"use client";

import { useEffect, useState } from "react";
import { X, Loader2 } from "lucide-react";
import { Button } from "./ui";

export function ScreenshotModal({ blobPath, onClose }: { blobPath: string; onClose: () => void }) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchUrl() {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://preorder-controller-678310400174.asia-southeast1.run.app";
        const res = await fetch(`${apiUrl}/signed-url?path=${encodeURIComponent(blobPath)}`);
        if (!res.ok) throw new Error("Failed to load signed URL");
        const data = await res.json();
        setImageUrl(data.signed_url);
      } catch (e: any) {
        setError(e.message);
      }
    }
    fetchUrl();
  }, [blobPath]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <div className="relative max-w-5xl w-full bg-[#111] border border-neutral-800 rounded-xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        <div className="flex justify-between items-center p-3 border-b border-neutral-800 bg-black/50">
          <span className="text-xs font-mono text-neutral-400 truncate w-[80%]">{blobPath.split("/").pop()}</span>
          <Button variant="ghost" onClick={onClose} className="h-8 px-2 text-neutral-400 hover:text-white">
            <X className="w-4 h-4" />
          </Button>
        </div>
        
        <div className="flex-1 overflow-auto p-4 flex items-center justify-center bg-black">
          {!imageUrl && !error && (
            <div className="flex flex-col items-center text-cyan-500 gap-2">
              <Loader2 className="w-8 h-8 animate-spin" />
              <span className="text-sm">Decrypting image from Cloud Storage...</span>
            </div>
          )}
          {error && <div className="text-rose-500">{error}</div>}
          {imageUrl && (
            <img 
              src={imageUrl} 
              alt="Bot Screenshot" 
              className="max-w-full h-auto rounded shadow-lg object-contain"
            />
          )}
        </div>
      </div>
    </div>
  );
}
