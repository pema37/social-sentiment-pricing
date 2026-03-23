"use client";

import React, { useState, useCallback, useRef, useMemo, useEffect } from "react";
import Image from "next/image";

const MAX_FILE_SIZE = 10 * 1024 * 1024;
const ACCEPTED_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"];

interface ScreenshotUploaderProps {
  onFileSelect: (file: File) => void;
  selectedFile: File | null;
  onClear: () => void;
  disabled: boolean;
}

export function ScreenshotUploader({
  onFileSelect,
  selectedFile,
  onClear,
  disabled,
}: ScreenshotUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const previewUrl = useMemo(() => {
    if (!selectedFile) return null;
    return URL.createObjectURL(selectedFile);
  }, [selectedFile]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const validateFile = useCallback((file: File): string | null => {
    if (!ACCEPTED_TYPES.includes(file.type)) {
      return "Invalid file type. Please upload PNG, JPEG, WebP, or GIF.";
    }
    if (file.size > MAX_FILE_SIZE) {
      return `File too large (${(file.size / 1024 / 1024).toFixed(1)}MB). Maximum is 10MB.`;
    }
    return null;
  }, []);

  const handleFileSelect = useCallback(
    (file: File) => {
      const error = validateFile(file);
      if (error) {
        setFileError(error);
        return;
      }
      setFileError(null);
      onFileSelect(file);
    },
    [onFileSelect, validateFile]
  );

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setIsDragging(true);
    } else if (e.type === "dragleave") {
      setIsDragging(false);
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
      const files = e.dataTransfer.files;
      if (files && files[0]) handleFileSelect(files[0]);
    },
    [handleFileSelect]
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files[0]) handleFileSelect(files[0]);
  };

  const handleClear = () => {
    setFileError(null);
    if (inputRef.current) inputRef.current.value = "";
    onClear();
  };

  if (selectedFile && previewUrl) {
    return (
      <div className="relative rounded-xl border-2 border-dashed border-emerald-500/50 bg-emerald-500/5 p-4">
        <div className="flex items-center gap-4">
          <div className="h-20 w-20 shrink-0 overflow-hidden rounded-lg bg-gray-100 dark:bg-gray-800">
            <Image
              src={previewUrl}
              alt="Selected screenshot"
              width={80}
              height={80}
              className="h-full w-full object-cover"
              unoptimized
            />
          </div>
          <div className="flex-1 min-w-0">
            <p className="truncate font-medium">{selectedFile.name}</p>
            <p className="text-sm text-muted-foreground">
              {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
            </p>
          </div>
          {!disabled && (
            <button
              onClick={handleClear}
              className="rounded px-3 py-1 text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            >
              Remove
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        className={`
          cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition-all
          ${isDragging ? "border-primary bg-primary/5" : "border-border hover:border-muted-foreground hover:bg-accent/30"}
          ${disabled ? "opacity-50 cursor-not-allowed" : ""}
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          onChange={handleChange}
          className="hidden"
          disabled={disabled}
        />
        <div className="flex flex-col items-center gap-3">
          <div className={`rounded-full px-4 py-2 text-sm font-medium ${isDragging ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground"}`}>
            {isDragging ? "Drop here" : "IMAGE"}
          </div>
          <div>
            <p className="font-medium">
              {isDragging ? "Drop screenshot here" : "Upload competitor screenshot"}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Drag and drop or click to browse — PNG, JPEG, WebP up to 10MB
            </p>
          </div>
        </div>
      </div>
      {fileError && (
        <div className="mt-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-2">
          <p className="text-sm text-destructive">{fileError}</p>
        </div>
      )}
    </div>
  );
}



