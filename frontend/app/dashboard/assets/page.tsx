"use client";

import { useState } from "react";
import { useEntities } from "@/hooks/useEntities";
import { AssetTable } from "@/components/dashboard/AssetTable";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// Simple tabs component (since Shadcn tabs might not be installed)
function SimpleTabs({
  defaultValue,
  children,
}: {
  defaultValue: string;
  children: React.ReactNode;
}) {
  return <div className="space-y-4">{children}</div>;
}

function SimpleTabsList({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex gap-2 border-b border-purple-500/20 pb-2">
      {children}
    </div>
  );
}

function SimpleTabsTrigger({
  value,
  activeValue,
  onValueChange,
  children,
}: {
  value: string;
  activeValue: string;
  onValueChange: (value: string) => void;
  children: React.ReactNode;
}) {
  const isActive = value === activeValue;
  return (
    <button
      onClick={() => onValueChange(value)}
      className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 ${
        isActive
          ? "border-purple-400 text-purple-300"
          : "border-transparent text-slate-400 hover:text-purple-300"
      }`}
    >
      {children}
    </button>
  );
}

function SimpleTabsContent({
  value,
  activeValue,
  children,
}: {
  value: string;
  activeValue: string;
  children: React.ReactNode;
}) {
  if (value !== activeValue) return null;
  return <div>{children}</div>;
}

export default function AssetDatabasePage() {
  const [activeTab, setActiveTab] = useState("locations");

  const { entities: locations, isLoading: locationsLoading } = useEntities(
    "anchor_location"
  );
  const { entities: keywords, isLoading: keywordsLoading } = useEntities(
    "seo_keyword"
  );
  const { entities: pages, isLoading: pagesLoading } = useEntities(
    "page_draft"
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-purple-400">Asset Database</h1>
        <p className="text-slate-400 mt-1">
          View and manage locations, keywords, and pages
        </p>
      </div>

      <Card className="border-purple-500/30 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="text-purple-300">Data Tables</CardTitle>
          <CardDescription className="text-slate-400">
            Real-time entity data from the system
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SimpleTabs defaultValue={activeTab}>
            <SimpleTabsList>
              <SimpleTabsTrigger
                value="locations"
                activeValue={activeTab}
                onValueChange={setActiveTab}
              >
                📍 Locations ({locations.length})
              </SimpleTabsTrigger>
              <SimpleTabsTrigger
                value="keywords"
                activeValue={activeTab}
                onValueChange={setActiveTab}
              >
                🔑 Keywords ({keywords.length})
              </SimpleTabsTrigger>
              <SimpleTabsTrigger
                value="pages"
                activeValue={activeTab}
                onValueChange={setActiveTab}
              >
                📄 Pages ({pages.length})
              </SimpleTabsTrigger>
            </SimpleTabsList>

            <SimpleTabsContent value="locations" activeValue={activeTab}>
              <div className="mt-4">
                <AssetTable
                  entities={locations}
                  entityType="anchor_location"
                  isLoading={locationsLoading}
                />
              </div>
            </SimpleTabsContent>

            <SimpleTabsContent value="keywords" activeValue={activeTab}>
              <div className="mt-4">
                <AssetTable
                  entities={keywords}
                  entityType="seo_keyword"
                  isLoading={keywordsLoading}
                />
              </div>
            </SimpleTabsContent>

            <SimpleTabsContent value="pages" activeValue={activeTab}>
              <div className="mt-4">
                <AssetTable
                  entities={pages}
                  entityType="page_draft"
                  isLoading={pagesLoading}
                />
              </div>
            </SimpleTabsContent>
          </SimpleTabs>
        </CardContent>
      </Card>
    </div>
  );
}
