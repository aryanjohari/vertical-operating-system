"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getAuthUser } from "@/lib/auth";
import { Save, Loader2 } from "lucide-react";

interface SettingsData {
  wp_url: string;
  wp_user: string;
  wp_password: string;
}

export default function SettingsPage() {
  const user_id = getAuthUser() || "admin";
  const [settings, setSettings] = useState<SettingsData>({
    wp_url: "",
    wp_user: "",
    wp_password: "",
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setIsLoading(true);
    try {
      const { getSettings } = await import("@/lib/api");
      const data = await getSettings(user_id);
      setSettings({
        wp_url: data.wp_url || "",
        wp_user: data.wp_user || "",
        wp_password: "", // Don't show password
      });
    } catch (error) {
      console.error("Error loading settings:", error);
      setSettings({
        wp_url: "",
        wp_user: "",
        wp_password: "",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setMessage(null);

    try {
      const { saveSettings } = await import("@/lib/api");
      const success = await saveSettings(user_id, {
        wp_url: settings.wp_url,
        wp_user: settings.wp_user,
        wp_password: settings.wp_password,
      });

      if (success) {
        setMessage({ type: "success", text: "Settings saved successfully!" });
        // Clear password field after save
        setSettings((prev) => ({ ...prev, wp_password: "" }));
      } else {
        setMessage({ type: "error", text: "Failed to save settings" });
      }
    } catch (error) {
      console.error("Error saving settings:", error);
      setMessage({ type: "error", text: "Error saving settings" });
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="p-4 md:p-6 lg:p-8 flex items-center justify-center min-h-full">
        <div className="text-center text-slate-400">
          <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2" />
          <p>Loading settings...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 lg:p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-purple-400">Settings</h1>
          <p className="text-slate-400 mt-1">Manage your system configuration</p>
        </div>

        {/* WordPress Settings */}
        <Card className="border-purple-500/30 bg-slate-900/50">
          <CardHeader>
            <CardTitle className="text-purple-400">WordPress Credentials</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSave} className="space-y-4">
              <div>
                <Label htmlFor="wp_url">WordPress URL *</Label>
                <Input
                  id="wp_url"
                  type="url"
                  value={settings.wp_url}
                  onChange={(e) => setSettings({ ...settings, wp_url: e.target.value })}
                  placeholder="https://yoursite.com"
                  required
                  className="bg-slate-800 border-purple-500/30 text-slate-100"
                />
                <p className="text-xs text-slate-500 mt-1">
                  Your WordPress site URL (e.g., https://yoursite.com)
                </p>
              </div>

              <div>
                <Label htmlFor="wp_user">WordPress Username *</Label>
                <Input
                  id="wp_user"
                  type="text"
                  value={settings.wp_user}
                  onChange={(e) => setSettings({ ...settings, wp_user: e.target.value })}
                  placeholder="admin"
                  required
                  className="bg-slate-800 border-purple-500/30 text-slate-100"
                />
              </div>

              <div>
                <Label htmlFor="wp_password">WordPress Password *</Label>
                <Input
                  id="wp_password"
                  type="password"
                  value={settings.wp_password}
                  onChange={(e) => setSettings({ ...settings, wp_password: e.target.value })}
                  placeholder={settings.wp_user ? "Enter new password to update" : "Enter password"}
                  required={!settings.wp_user}
                  className="bg-slate-800 border-purple-500/30 text-slate-100"
                />
                <p className="text-xs text-slate-500 mt-1">
                  {settings.wp_user
                    ? "Leave blank to keep current password, or enter new password to update"
                    : "Password for WordPress API authentication"}
                </p>
              </div>

              {message && (
                <div
                  className={`p-3 rounded-md ${
                    message.type === "success"
                      ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                      : "bg-red-500/20 text-red-400 border border-red-500/30"
                  }`}
                >
                  {message.text}
                </div>
              )}

              <Button
                type="submit"
                disabled={isSaving}
                className="bg-purple-600 hover:bg-purple-700 text-white"
              >
                {isSaving ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save className="w-4 h-4 mr-2" />
                    Save Settings
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Info Card */}
        <Card className="border-slate-700/50 bg-slate-900/30">
          <CardContent className="pt-6">
            <p className="text-sm text-slate-400">
              <strong className="text-slate-300">Note:</strong> These credentials are used to publish
              content to your WordPress site. Make sure to use an application password or a user with
              appropriate permissions.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
