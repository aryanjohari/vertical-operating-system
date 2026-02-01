"use client";

import React from "react";
import { UseFormRegister, FieldValues, Path, FieldError } from "react-hook-form";
import Input from "@/components/ui/Input";

type FormInputProps<T extends FieldValues> = {
  label: string;
  name: Path<T>;
  register: UseFormRegister<T>;
  error?: FieldError;
  type?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  className?: string;
};

export default function FormInput<T extends FieldValues>({
  label,
  name,
  register,
  error,
  type = "text",
  placeholder,
  required,
  disabled,
  className = "",
}: FormInputProps<T>) {
  return (
    <Input
      label={label}
      type={type}
      placeholder={placeholder}
      disabled={disabled}
      className={className}
      error={error?.message}
      {...register(name, { required: required ? `${label} is required` : false })}
    />
  );
}
