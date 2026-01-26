// app/(dashboard)/onboarding/page.tsx
'use client';

import { useState } from 'react';
import React from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import api, { pollContextUntilComplete } from '@/lib/api';
import Card from '@/components/ui/Card';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';

type Step = 1 | 2 | 3;

interface ModuleOption {
  id: string;
  name: string;
  description: string;
  icon: React.ReactElement;
}

interface BusinessFormData {
  businessName: string;
  niche: string;
  phone: string;
  email: string;
  website: string;
  description: string;
}

const NICHE_OPTIONS = [
  'Plumber',
  'Lawyer',
  'Electrician',
  'HVAC',
  'Roofing',
  'Carpenter',
  'Painter',
  'Landscaper',
  'Accountant',
  'Real Estate Agent',
  'Dentist',
  'Veterinarian',
  'Auto Repair',
  'Other',
];

const MODULES: ModuleOption[] = [
  {
    id: 'local_seo',
    name: 'Growth Engine (pSEO)',
    description: 'Dominate Google Maps',
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    id: 'lead_gen',
    name: 'Lead Hunter (Sniper)',
    description: 'Active Lead Gen & Speed Bridge',
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    ),
  },
  {
    id: 'admin',
    name: 'Admin Suite',
    description: 'Invoicing & Compliance',
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
  },
];

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>(1);
  const [selectedModules, setSelectedModules] = useState<string[]>([]);
  const [isCompiling, setIsCompiling] = useState(false);
  const [compileLogs, setCompileLogs] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<BusinessFormData>();

  const handleModuleToggle = (moduleId: string) => {
    setSelectedModules((prev) =>
      prev.includes(moduleId)
        ? prev.filter((id) => id !== moduleId)
        : [...prev, moduleId]
    );
  };

  const handleStep1Next = () => {
    if (selectedModules.length === 0) {
      setError('Please select at least one module');
      return;
    }
    setError(null);
    setStep(2);
  };

  const handleStep2Next = handleSubmit(async (data) => {
    if (!data.businessName || !data.niche) {
      setError('Business Name and Niche are required');
      return;
    }
    setError(null);
    setStep(3);
    await compileProfile(data);
  });

  const compileProfile = async (formData: BusinessFormData) => {
    setIsCompiling(true);
    setError(null);
    setCompileLogs([]);

    const addLog = (message: string) => {
      setCompileLogs((prev) => [...prev, message]);
    };

    try {
      // Step A: Scrape (if website provided)
      if (formData.website) {
        addLog('Scraping URL...');
        await new Promise((resolve) => setTimeout(resolve, 1000)); // Simulate scraping
      }

      addLog('Analyzing Niche...');
      await new Promise((resolve) => setTimeout(resolve, 500));

      addLog('Compiling DNA...');
      
      const response = await api.post('/api/run', {
        task: 'onboarding',
        user_id: '',
        params: {
          action: 'compile_profile',
          identity: {
            business_name: formData.businessName,
            niche: formData.niche,
            phone: formData.phone || '',
            email: formData.email || '',
            website: formData.website || '',
            description: formData.description || '',
          },
          modules: selectedModules,
        },
      });

      // Handle async response (onboarding is now async)
      if (response.data.status === 'processing') {
        const contextId = response.data.data?.context_id;
        if (contextId) {
          addLog('Generating your project DNA...');
          
          try {
            // Poll for completion
            const result = await pollContextUntilComplete(contextId, 120, 2000); // 4 minutes max
            
            if (result && result.status === 'success') {
              addLog('Saving Profile...');
              await new Promise((resolve) => setTimeout(resolve, 500));

              addLog('Injecting Wisdom into RAG...');
              await new Promise((resolve) => setTimeout(resolve, 500));

              addLog('Project Created ✓');

              // Redirect to dashboard after a brief delay
              setTimeout(() => {
                const projectId = result.data?.project_id || response.data.data?.project_id;
                if (projectId) {
                  router.push(`/projects/${projectId}`);
                } else {
                  router.push('/dashboard');
                }
              }, 1000);
            } else {
              throw new Error(result?.message || 'Compilation failed');
            }
          } catch (error: any) {
            throw new Error(error.message || 'Compilation timed out or failed');
          }
        } else {
          throw new Error('No context ID received for async task');
        }
      } else if (response.data.status === 'error') {
        throw new Error(response.data.message || 'Compilation failed');
      } else if (response.data.status === 'success') {
        // Sync completion (shouldn't happen for onboarding, but handle it)
        addLog('Saving Profile...');
        await new Promise((resolve) => setTimeout(resolve, 500));

        addLog('Injecting Wisdom into RAG...');
        await new Promise((resolve) => setTimeout(resolve, 500));

        addLog('Project Created ✓');

        // Redirect to dashboard after a brief delay
        setTimeout(() => {
          const projectId = response.data.data?.project_id;
          if (projectId) {
            router.push(`/projects/${projectId}`);
          } else {
            router.push('/dashboard');
          }
        }, 1000);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to compile profile. Please try again.');
      addLog('✗ Error: ' + (err.message || 'Compilation failed'));
    } finally {
      setIsCompiling(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-green-400 font-mono">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-4xl font-bold mb-2 text-green-400">GENESIS</h1>
          <p className="text-gray-400 text-sm">Apex Profile Compiler v3.0</p>
        </div>

        {/* Step 1: Module Selection */}
        {step === 1 && (
          <Card className="bg-gray-800 border-gray-700">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-green-400 mb-2">Step 1: Engine Selection</h2>
              <p className="text-gray-400 text-sm">Select the modules you want to activate</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              {MODULES.map((module) => (
                <div
                  key={module.id}
                  onClick={() => handleModuleToggle(module.id)}
                  className={`p-6 rounded-lg border-2 cursor-pointer transition-all ${
                    selectedModules.includes(module.id)
                      ? 'border-green-500 bg-green-500/10'
                      : 'border-gray-700 hover:border-gray-600'
                  }`}
                >
                  <div className="flex items-center gap-3 mb-3">
                    <div className={selectedModules.includes(module.id) ? 'text-green-400' : 'text-gray-500'}>
                      {module.icon}
                    </div>
                    <div className="flex items-center">
                      <input
                        type="checkbox"
                        checked={selectedModules.includes(module.id)}
                        onChange={() => handleModuleToggle(module.id)}
                        className="mr-2 w-4 h-4 text-green-600 bg-gray-700 border-gray-600 rounded focus:ring-green-500"
                      />
                      <span className="text-white font-semibold">{module.name}</span>
                    </div>
                  </div>
                  <p className="text-gray-400 text-sm">{module.description}</p>
                </div>
              ))}
            </div>

            {error && (
              <div className="mb-4 p-3 bg-red-900/20 border border-red-500 rounded text-red-400 text-sm">
                {error}
              </div>
            )}

            <Button
              onClick={handleStep1Next}
              disabled={selectedModules.length === 0}
              variant="primary"
              className="w-full"
            >
              Next: Business DNA
            </Button>
          </Card>
        )}

        {/* Step 2: Business DNA Form */}
        {step === 2 && (
          <Card className="bg-gray-800 border-gray-700">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-green-400 mb-2">Step 2: Business DNA</h2>
              <p className="text-gray-400 text-sm">Tell us about your business</p>
            </div>

            <form onSubmit={handleStep2Next} className="space-y-4">
              <Input
                label="Business Name *"
                {...register('businessName', { required: 'Business name is required' })}
                error={errors.businessName?.message}
                className="bg-gray-900 text-white"
              />

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Niche *
                </label>
                <select
                  {...register('niche', { required: 'Niche is required' })}
                  className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 bg-gray-900 border-gray-700 text-white"
                >
                  <option value="">Select a niche...</option>
                  {NICHE_OPTIONS.map((niche) => (
                    <option key={niche} value={niche}>
                      {niche}
                    </option>
                  ))}
                </select>
                {errors.niche && (
                  <p className="mt-1 text-sm text-red-400">{errors.niche.message}</p>
                )}
              </div>

              <Input
                label="Phone"
                type="tel"
                {...register('phone')}
                className="bg-gray-900 text-white"
              />

              <Input
                label="Email"
                type="email"
                {...register('email')}
                className="bg-gray-900 text-white"
              />

              <Input
                label="Website URL"
                type="url"
                {...register('website')}
                placeholder="https://example.com"
                className="bg-gray-900 text-white"
              />

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  One Sentence Pitch
                </label>
                <textarea
                  {...register('description')}
                  rows={3}
                  className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 bg-gray-900 border-gray-700 text-white"
                  placeholder="Describe your business in one sentence..."
                />
              </div>

              {error && (
                <div className="p-3 bg-red-900/20 border border-red-500 rounded text-red-400 text-sm">
                  {error}
                </div>
              )}

              <div className="flex gap-4">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setStep(1)}
                  className="flex-1"
                >
                  Back
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  disabled={isCompiling}
                  className="flex-1"
                >
                  Compile Profile
                </Button>
              </div>
            </form>
          </Card>
        )}

        {/* Step 3: Genesis Loading */}
        {step === 3 && (
          <Card className="bg-gray-800 border-gray-700">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-green-400 mb-2">Step 3: Genesis</h2>
              <p className="text-gray-400 text-sm">Compiling your profile...</p>
            </div>

            <div className="bg-gray-900 rounded-lg p-6 font-mono text-sm">
              <div className="space-y-2">
                {compileLogs.map((log, index) => (
                  <div key={index} className="text-green-400">
                    <span className="text-gray-500">$</span> {log}
                  </div>
                ))}
                {isCompiling && (
                  <div className="text-green-400 flex items-center gap-2">
                    <span className="text-gray-500">$</span>
                    <span className="animate-pulse">_</span>
                  </div>
                )}
              </div>
            </div>

            {error && (
              <div className="mt-4 p-3 bg-red-900/20 border border-red-500 rounded text-red-400 text-sm">
                {error}
              </div>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}
