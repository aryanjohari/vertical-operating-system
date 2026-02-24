"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { cn } from "@/lib/utils";
import type { FormSchema, FormSchemaField } from "@/lib/api";

const inputClass = cn(
  "w-full rounded border border-border bg-muted/50 px-3 py-2 text-foreground placeholder:text-muted-foreground",
  "focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background",
  "disabled:cursor-not-allowed disabled:opacity-60"
);

function getAtPath(obj: Record<string, unknown>, path: string): unknown {
  const keys = path.split(".");
  let cur: unknown = obj;
  for (const k of keys) {
    cur = (cur as Record<string, unknown>)?.[k];
  }
  return cur;
}

function setAtPath(
  obj: Record<string, unknown>,
  path: string,
  value: unknown
): Record<string, unknown> {
  const keys = path.split(".");
  const out = JSON.parse(JSON.stringify(obj));
  let cur: Record<string, unknown> = out;
  for (let i = 0; i < keys.length - 1; i++) {
    const k = keys[i];
    if (!(k in cur) || typeof cur[k] !== "object" || cur[k] === null) {
      cur[k] = {};
    }
    cur = cur[k] as Record<string, unknown>;
  }
  cur[keys[keys.length - 1]] = value;
  return out;
}

function toList(val: unknown): string[] {
  if (Array.isArray(val)) return val.map((x) => String(x ?? "").trim()).filter(Boolean);
  if (val == null) return [];
  const s = String(val).trim();
  if (!s) return [];
  return s
    .replace(/,/g, "\n")
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);
}

interface DynamicFormProps {
  schema?: FormSchema | null;
  defaults?: Record<string, unknown> | null;
  schemaType?: "profile" | "pseo" | "lead_gen";
  onSubmit: (payload: Record<string, unknown>) => Promise<void>;
  submitLabel?: string;
  loading?: boolean;
  extraFields?: React.ReactNode;
  onCancel?: () => void;
}

export function DynamicForm({
  schema: schemaProp,
  defaults: defaultsProp,
  schemaType,
  onSubmit,
  submitLabel = "Save",
  loading = false,
  extraFields,
  onCancel,
}: DynamicFormProps) {
  const [schema, setSchema] = useState<FormSchema | null>(schemaProp ?? null);
  const [, setDefaults] = useState<Record<string, unknown>>(
    (defaultsProp ?? {}) as Record<string, unknown>
  );
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [fetchError, setFetchError] = useState<string | null>(null);
  const appliedRef = useRef<{ schema: FormSchema | null; defaults: Record<string, unknown> | null }>({
    schema: null,
    defaults: null,
  });

  const loadSchema = useCallback(async () => {
    if (!schemaType) return;
    try {
      const { getFormSchema } = await import("@/lib/api");
      const res = await getFormSchema(schemaType);
      setSchema(res.schema);
      setDefaults((res.defaults ?? {}) as Record<string, unknown>);
      setValues((res.defaults ?? {}) as Record<string, unknown>);
      setFetchError(null);
    } catch (e) {
      setFetchError(e instanceof Error ? e.message : "Failed to load form");
    }
  }, [schemaType]);

  useEffect(() => {
    if (schemaProp) setSchema(schemaProp);
    const nextDefaults =
      defaultsProp != null &&
      typeof defaultsProp === "object" &&
      !Array.isArray(defaultsProp)
        ? (defaultsProp as Record<string, unknown>)
        : null;
    if (nextDefaults) {
      if (
        appliedRef.current.schema !== schemaProp ||
        appliedRef.current.defaults !== defaultsProp
      ) {
        appliedRef.current = { schema: schemaProp ?? null, defaults: nextDefaults };
        setDefaults(nextDefaults);
        setValues(nextDefaults);
      }
    } else {
      appliedRef.current = { schema: null, defaults: null };
    }
  }, [schemaProp, defaultsProp]);

  useEffect(() => {
    if (schemaType && !schemaProp) loadSchema();
  }, [schemaType, schemaProp, loadSchema]);

  const update = useCallback((path: string, value: unknown) => {
    setValues((prev) => setAtPath(prev, path, value));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Convert array-of-string fields that are stored as string (from textarea) back to array for API
    let payload: Record<string, unknown> = JSON.parse(JSON.stringify(values));
    if (schema?.fields) {
      for (const f of schema.fields) {
        if (f.type === "array" && f.itemType === "string") {
          const v = getAtPath(payload, f.path);
          if (typeof v === "string") payload = setAtPath(payload, f.path, v.split("\n"));
        }
      }
    }
    await onSubmit(payload);
  };

  if (fetchError) {
    return (
      <div className="rounded border border-red-500/50 bg-red-500/10 p-4 text-sm text-red-400">
        {fetchError}
      </div>
    );
  }
  if (!schema) {
    return (
      <div className="animate-pulse rounded bg-muted p-4 text-muted-foreground">
        Loading form...
      </div>
    );
  }

  const sections = schema.sections ?? {};

  /** Group section fields by field.group so YAML structure (e.g. Local SEO, Lead Gen) is visible. */
  function groupFields(fields: FormSchemaField[]): { group: string; fields: FormSchemaField[] }[] {
    const byGroup = new Map<string, FormSchemaField[]>();
    for (const f of fields) {
      const g = f.group ?? "";
      if (!byGroup.has(g)) byGroup.set(g, []);
      byGroup.get(g)!.push(f);
    }
    const order = Array.from(byGroup.keys()).sort((a, b) => (a === "" ? -1 : b === "" ? 1 : a.localeCompare(b)));
    return order.map((group) => ({ group, fields: byGroup.get(group)! }));
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      {Object.entries(sections).map(([sectionKey, sectionFields]) => (
        <section key={sectionKey} className="space-y-4">
          <h3 className="text-sm font-semibold text-foreground">
            {sectionKey.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
          </h3>
          {groupFields(sectionFields).map(({ group, fields: groupFieldsList }) => (
            <div key={group || "_"} className="space-y-2">
              {group && (
                <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  {group}
                </h4>
              )}
              <div className={group ? "ml-2 space-y-2 border-l-2 border-border/50 pl-3" : "space-y-2"}>
                {groupFieldsList.map((f) => (
                  <Field
                    key={f.path}
                    field={f}
                    value={getAtPath(values, f.path)}
                    onChange={(v) => update(f.path, v)}
                    disabled={loading}
                    inputClass={inputClass}
                  />
                ))}
              </div>
            </div>
          ))}
        </section>
      ))}
      {extraFields}
      <div className="flex justify-end gap-2">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="rounded border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-60"
          >
            Cancel
          </button>
        )}
        <button
          type="submit"
          disabled={loading}
          className="acid-glow rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? "Saving..." : submitLabel}
        </button>
      </div>
    </form>
  );
}

function Field({
  field,
  value,
  onChange,
  disabled,
  inputClass,
}: {
  field: FormSchemaField;
  value: unknown;
  onChange: (v: unknown) => void;
  disabled: boolean;
  inputClass: string;
}) {
  const label = field.label ?? field.path.split(".").pop()?.replace(/_/g, " ") ?? field.path;
  const def = field.default;

  if (field.type === "boolean") {
    return (
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={Boolean(value ?? def ?? false)}
          onChange={(e) => onChange(e.target.checked)}
          disabled={disabled}
          className="rounded border-border"
        />
        <span className="text-sm text-foreground">{label}</span>
      </label>
    );
  }

  if (field.type === "number") {
    return (
      <div>
        <label className="block text-xs font-medium text-muted-foreground">{label}</label>
        <input
          type="number"
          value={Number(value ?? def ?? 0)}
          onChange={(e) => onChange(parseInt(e.target.value, 10) || 0)}
          disabled={disabled}
          className={cn(inputClass, "mt-1")}
        />
      </div>
    );
  }

  if (field.type === "array" && field.itemType === "string") {
    // Preserve blank lines: if value is string (user typing), show as-is; else derive from array
    const str =
      typeof value === "string"
        ? value
        : Array.isArray(value)
          ? (value as string[]).join("\n")
          : toList(value ?? def).join("\n");
    return (
      <div>
        <label className="block text-xs font-medium text-muted-foreground">
          {label} {field.required ? "*" : ""} (one per line)
        </label>
        <textarea
          value={str}
          onChange={(e) => onChange(e.target.value)}
          rows={4}
          disabled={disabled}
          className={cn(inputClass, "mt-1 font-mono text-sm")}
        />
      </div>
    );
  }

  if (field.type === "array" && field.itemType === "object" && field.itemSchema?.length) {
    const arr = Array.isArray(value) ? value : (Array.isArray(def) ? def : []);
    const basePath = field.path;
    const itemSchema = field.itemSchema;

    const makeDefaultItem = (): Record<string, unknown> => {
      const obj: Record<string, unknown> = {};
      for (const sub of itemSchema) {
        const key = sub.path.split(".").pop() ?? sub.path;
        obj[key] = sub.default ?? (sub.type === "array" ? [] : sub.type === "boolean" ? false : "");
      }
      return obj;
    };

    const addItem = () => {
      const next = [...arr, makeDefaultItem()];
      onChange(next);
    };
    const removeItem = (i: number) => {
      const next = arr.filter((_, idx) => idx !== i);
      onChange(next);
    };

    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="block text-xs font-medium text-muted-foreground">
            {label} {field.required ? "*" : ""}
          </label>
          <button
            type="button"
            onClick={addItem}
            disabled={disabled}
            className="text-xs text-primary hover:underline disabled:opacity-60"
          >
            + Add
          </button>
        </div>
        <div className="space-y-3">
          {arr.map((_, i) => (
            <div
              key={i}
              className="rounded border border-border bg-muted/20 p-3 space-y-2"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-muted-foreground">
                  #{i + 1}
                </span>
                {arr.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeItem(i)}
                    disabled={disabled}
                    className="text-xs text-destructive hover:underline disabled:opacity-60"
                  >
                    Remove
                  </button>
                )}
              </div>
              <div className="grid gap-2">
                {itemSchema.map((sub) => {
                  const subPath = `${basePath}.${i}.${sub.path}`;
                  const item = arr[i] ?? {};
                  return (
                    <Field
                      key={subPath}
                      field={sub}
                      value={getAtPath(
                        item as Record<string, unknown>,
                        sub.path
                      )}
                      onChange={(v: unknown) => {
                        const next = JSON.parse(JSON.stringify(arr));
                        if (!next[i]) next[i] = makeDefaultItem();
                        const parts = sub.path.split(".");
                        let cur: Record<string, unknown> = next[i] as Record<string, unknown>;
                        for (let j = 0; j < parts.length - 1; j++) {
                          const k = parts[j];
                          if (!(k in cur) || typeof cur[k] !== "object") cur[k] = {};
                          cur = cur[k] as Record<string, unknown>;
                        }
                        cur[parts[parts.length - 1]] = v;
                        onChange(next);
                      }}
                      disabled={disabled}
                      inputClass={inputClass}
                    />
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (field.type === "string" && field.multiline) {
    const str = String(value ?? def ?? "");
    return (
      <div>
        <label className="block text-xs font-medium text-muted-foreground">
          {label} {field.required ? "*" : ""}
        </label>
        <textarea
          value={str}
          onChange={(e) => onChange(e.target.value)}
          rows={5}
          disabled={disabled}
          placeholder={field.required ? "Required" : ""}
          className={cn(inputClass, "mt-1 min-h-[100px]")}
        />
      </div>
    );
  }

  return (
    <div>
      <label className="block text-xs font-medium text-muted-foreground">
        {label} {field.required ? "*" : ""}
      </label>
      <input
        type="text"
        value={String(value ?? def ?? "")}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder={field.required ? "Required" : ""}
        className={cn(inputClass, "mt-1")}
      />
    </div>
  );
}
