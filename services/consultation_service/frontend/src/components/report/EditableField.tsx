import { useState } from "react";
import { formatMoney } from "./format";

interface EditableFieldProps {
  value: string;
  onChange?: (value: string) => void;
  editable: boolean;
  placeholder?: string;
  multiline?: boolean;
  money?: boolean;
  className?: string;
}

/**
 * Значение поля отчёта. В интерактивном режиме (editable=true) клик по значению
 * превращает его в инпут того же вида; в print-режиме (editable=false) — просто текст,
 * тот же компонент, чтобы дизайн не расходился между сайтом и PDF.
 */
export function EditableField({
  value,
  onChange,
  editable,
  placeholder = "Уточняется",
  multiline = false,
  money = false,
  className = "",
}: EditableFieldProps) {
  const [isEditing, setIsEditing] = useState(false);

  if (editable && isEditing) {
    const commonProps = {
      autoFocus: true,
      className: "field-input",
      value,
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => onChange?.(e.target.value),
      onBlur: () => setIsEditing(false),
    };
    return multiline ? (
      <textarea {...commonProps} rows={3} />
    ) : (
      <input {...commonProps} type="text" />
    );
  }

  const display = value.trim() ? (money ? formatMoney(value) : value) : placeholder;
  const isEmpty = !value.trim();

  return (
    <span
      className={`editable-value ${isEmpty ? "is-empty" : ""} ${className}`}
      onClick={editable ? () => setIsEditing(true) : undefined}
      role={editable ? "button" : undefined}
      tabIndex={editable ? 0 : undefined}
    >
      {display}
    </span>
  );
}
