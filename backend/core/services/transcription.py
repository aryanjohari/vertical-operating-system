"""
Transcription service using Google Gemini API.
Downloads recordings from Twilio, transcribes with Gemini, and deletes recordings to minimize costs.
"""
import logging
import os
import tempfile
import requests
from typing import Optional, Tuple
from twilio.rest import Client
from google import genai
from google.genai import types

logger = logging.getLogger("Apex.Transcription")


class TranscriptionService:
    """
    Handles call transcription using Google Gemini.
    Downloads MP3 from Twilio, transcribes, and optionally deletes the recording.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("Apex.Transcription")
        
        # Initialize Gemini client (same pattern as llm_gateway)
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set.")
        
        self.gemini_client = genai.Client(api_key=google_api_key)
        self.model = os.getenv("APEX_LLM_MODEL", "gemini-2.5-flash-lite")
        
        # Initialize Twilio client (for deleting recordings)
        twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        if twilio_sid and twilio_token:
            self.twilio_client = Client(twilio_sid, twilio_token)
        else:
            self.twilio_client = None
            self.logger.warning("⚠️ Twilio credentials not set. Recording deletion will be skipped.")
    
    def transcribe_recording(
        self,
        recording_url: str,
        call_sid: str,
        delete_after_transcription: bool = True
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Downloads MP3 from Twilio, transcribes with Gemini, and optionally deletes recording.
        
        Args:
            recording_url: Full URL to the MP3 recording (e.g., https://api.twilio.com/.../Recording.mp3)
            call_sid: Twilio Call SID (for deleting the recording)
            delete_after_transcription: If True, delete the recording from Twilio after transcription
        
        Returns:
            Tuple of (transcription_text, error_message)
            - transcription_text: The transcribed text, or None if failed
            - error_message: Error message if failed, or None if successful
        """
        temp_file = None
        recording_sid = None
        
        try:
            # 1. Extract recording SID from URL for deletion
            # URL format: https://api.twilio.com/2010-04-01/Accounts/{AccountSid}/Recordings/{RecordingSid}.mp3
            try:
                parts = recording_url.split('/Recordings/')
                if len(parts) > 1:
                    recording_sid = parts[1].replace('.mp3', '')
                    self.logger.info(f"📼 Recording SID: {recording_sid}")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not extract recording SID from URL: {e}")
            
            # 2. Download MP3 file (with Twilio authentication if needed)
            self.logger.info(f"⬇️ Downloading recording from: {recording_url}")
            
            # Twilio recording URLs require Basic Auth with Account SID and Auth Token
            auth = None
            if self.twilio_client:
                # Extract credentials from Twilio client
                twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
                twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
                if twilio_sid and twilio_token:
                    from requests.auth import HTTPBasicAuth
                    auth = HTTPBasicAuth(twilio_sid, twilio_token)
            
            response = requests.get(recording_url, stream=True, timeout=30, auth=auth)
            response.raise_for_status()
            
            # 3. Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
            
            file_size = os.path.getsize(temp_file_path)
            self.logger.info(f"✅ Downloaded {file_size / 1024:.2f} KB to {temp_file_path}")
            
            # 4. Transcribe with Google Gemini
            self.logger.info(f"🎤 Transcribing with Google Gemini ({self.model})...")
            
            # Upload file to Gemini using client's files API
            # Open file and upload using the client (consistent with llm_gateway pattern)
            with open(temp_file_path, 'rb') as audio_file:
                try:
                    # Try with config first (if UploadFileConfig exists)
                    uploaded_file = self.gemini_client.files.upload(
                        file=audio_file,
                        config=types.UploadFileConfig(
                            mime_type="audio/mpeg",
                            display_name="call_recording.mp3"
                        )
                    )
                except (TypeError, AttributeError):
                    # Fallback: try without config (simpler API)
                    audio_file.seek(0)  # Reset file pointer
                    uploaded_file = self.gemini_client.files.upload(file=audio_file)
            self.logger.debug(f"📤 Uploaded file to Gemini: {uploaded_file.name}")
            
            try:
                # Wait for file to be processed (Gemini needs time)
                import time
                time.sleep(1)  # Brief wait for file processing
                
                # Request transcription from Gemini
                prompt = "Please transcribe this phone call recording verbatim. Return only the transcription text, no additional commentary, formatting, or explanations."
                
                response = self.gemini_client.models.generate_content(
                    model=self.model,
                    contents=[
                        types.Part.from_uri(
                            file_uri=uploaded_file.uri,
                            mime_type="audio/mpeg"
                        ),
                        prompt
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.1,  # Low temperature for accurate transcription
                    )
                )
                
                transcription_text = (response.text or "").strip()
                
                if not transcription_text:
                    raise ValueError("Empty transcription response from Gemini")
                
                self.logger.info(f"✅ Transcription complete: {len(transcription_text)} characters")
                
            finally:
                # Clean up uploaded file from Gemini
                try:
                    self.gemini_client.files.delete(name=uploaded_file.name)
                    self.logger.debug(f"🗑️ Deleted uploaded file from Gemini: {uploaded_file.name}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to delete uploaded file from Gemini: {e}")
            
            # 5. Delete recording from Twilio (to minimize storage costs)
            if delete_after_transcription and recording_sid and self.twilio_client:
                try:
                    self.twilio_client.recordings(recording_sid).delete()
                    self.logger.info(f"🗑️ Deleted recording {recording_sid} from Twilio")
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to delete recording {recording_sid}: {e}")
                    # Don't fail the whole operation if deletion fails
            
            return transcription_text, None
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to download recording: {e}"
            self.logger.error(f"❌ {error_msg}")
            return None, error_msg
            
        except Exception as e:
            error_msg = f"Failed to transcribe recording: {e}"
            self.logger.error(f"❌ {error_msg}", exc_info=True)
            return None, error_msg
            
        finally:
            # Clean up temporary file
            if temp_file and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                    self.logger.debug(f"Cleaned up temp file: {temp_file_path}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to delete temp file: {e}")


# Global instance
transcription_service = TranscriptionService()
