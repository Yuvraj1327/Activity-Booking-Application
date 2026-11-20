"use client";

import { Camera, Trash2 } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import { saveAvatarPath, updateProfile } from "@/app/(dashboard)/settings/actions";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getSupabaseClient } from "@/lib/supabase/client";
import type { MyProfile } from "@/lib/types";

const BUCKET = "profile-images"; // private; own-folder policy: <user id>/<name>.<ext>
const MAX_BYTES = 2 * 1024 * 1024; // matches the bucket limit
const TYPES: Record<string, string> = { "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp" };

type Msg = { ok: boolean; text: string } | null;

export function ProfileSection({ profile, email, avatarUrl }: { profile: MyProfile; email: string | null; avatarUrl: string | null }) {
  const [current, setCurrent] = useState(profile);
  const [photo, setPhoto] = useState<string | null>(avatarUrl);
  const [name, setName] = useState(profile.full_name);
  const [phone, setPhone] = useState(profile.phone ?? "");
  const [saving, setSaving] = useState(false);
  const [photoBusy, setPhotoBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  const [photoMsg, setPhotoMsg] = useState<Msg>(null);
  const [errors, setErrors] = useState<{ name?: string; phone?: string }>({});
  const fileRef = useRef<HTMLInputElement>(null);

  const initials = (current.full_name.split(/\s+/).map((w) => w[0]).slice(0, 2).join("") || "A").toUpperCase();
  const dirty = name.trim() !== current.full_name || phone.trim() !== (current.phone ?? "");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const next: typeof errors = {};
    if (!name.trim()) next.name = "Enter your name.";
    else if (name.trim().length > 120) next.name = "Name must be 120 characters or fewer.";
    if (phone.trim() && !/^\+[1-9][0-9]{6,14}$/.test(phone.trim())) next.phone = "Use international format, e.g. +919876543210.";
    setErrors(next);
    if (Object.keys(next).length) return;
    setSaving(true);
    setMsg(null);
    const res = await updateProfile({ full_name: name, phone });
    setSaving(false);
    if (res.ok && res.data) {
      setCurrent(res.data);
      setName(res.data.full_name);
      setPhone(res.data.phone ?? "");
    }
    setMsg({ ok: res.ok, text: res.message });
  }

  async function onPickFile(file: File | undefined) {
    if (!file) return;
    setPhotoMsg(null);
    const ext = TYPES[file.type];
    if (!ext) return setPhotoMsg({ ok: false, text: "Choose a JPG, PNG or WebP image." });
    if (file.size > MAX_BYTES) return setPhotoMsg({ ok: false, text: "That image is larger than 2 MB. Choose a smaller one." });
    const supabase = getSupabaseClient();
    if (!supabase) return setPhotoMsg({ ok: false, text: "Photo upload is not configured." });

    setPhotoBusy(true);
    const path = `${current.id}/avatar-${Date.now()}.${ext}`;
    const up = await supabase.storage.from(BUCKET).upload(path, file, { contentType: file.type, upsert: false });
    if (up.error) {
      setPhotoBusy(false);
      return setPhotoMsg({ ok: false, text: "Could not upload the image. Please try again." });
    }
    const saved = await saveAvatarPath(path);
    if (!saved.ok) {
      await supabase.storage.from(BUCKET).remove([path]); // do not leave an orphan
      setPhotoBusy(false);
      return setPhotoMsg({ ok: false, text: saved.message });
    }
    const old = current.avatar_path;
    if (old) await supabase.storage.from(BUCKET).remove([old]); // best effort
    const signed = await supabase.storage.from(BUCKET).createSignedUrl(path, 3600);
    setPhoto(signed.data?.signedUrl ?? null);
    if (saved.data) setCurrent(saved.data);
    setPhotoBusy(false);
    setPhotoMsg({ ok: true, text: saved.message });
    if (fileRef.current) fileRef.current.value = "";
  }

  async function onRemovePhoto() {
    setPhotoBusy(true);
    setPhotoMsg(null);
    const old = current.avatar_path;
    const saved = await saveAvatarPath(null);
    if (saved.ok) {
      if (old) await getSupabaseClient()?.storage.from(BUCKET).remove([old]); // best effort
      setPhoto(null);
      if (saved.data) setCurrent(saved.data);
    }
    setPhotoBusy(false);
    setPhotoMsg({ ok: saved.ok, text: saved.message });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Profile</CardTitle>
        <CardDescription>Your name and photo are shown to other administrators and in the audit log.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex flex-wrap items-center gap-4">
          {photo ? (
            // eslint-disable-next-line @next/next/no-img-element -- short-lived signed URL, not optimisable
            <img src={photo} alt="Your profile photo" className="size-20 rounded-full border border-border object-cover" />
          ) : (
            <span aria-hidden className="flex size-20 items-center justify-center rounded-full bg-primary-tint text-xl font-semibold text-primary">{initials}</span>
          )}
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" id="avatar-file" data-testid="avatar-input" onChange={(e) => onPickFile(e.target.files?.[0])} />
              <Button type="button" variant="outline" size="sm" disabled={photoBusy} onClick={() => fileRef.current?.click()}>
                <Camera className="size-4" aria-hidden />
                {photoBusy ? "Working..." : photo ? "Change photo" : "Upload photo"}
              </Button>
              {current.avatar_path && (
                <Button type="button" variant="ghost" size="sm" disabled={photoBusy} onClick={onRemovePhoto}>
                  <Trash2 className="size-4" aria-hidden />
                  Remove
                </Button>
              )}
            </div>
            <p className="text-xs text-muted-foreground">JPG, PNG or WebP, up to 2 MB.</p>
          </div>
        </div>
        {photoMsg && <Alert variant={photoMsg.ok ? "info" : "error"}>{photoMsg.text}</Alert>}

        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <div className="space-y-1.5">
            <Label htmlFor="full_name">Full name</Label>
            <Input id="full_name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} autoComplete="name" aria-invalid={!!errors.name} aria-describedby={errors.name ? "full_name-err" : undefined} />
            {errors.name && <p id="full_name-err" className="text-xs text-destructive">{errors.name}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" value={email ?? ""} readOnly disabled />
            <p className="text-xs text-muted-foreground">Your sign-in email cannot be changed here.</p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="phone">Phone (optional)</Label>
            <Input id="phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+919876543210" autoComplete="tel" aria-invalid={!!errors.phone} aria-describedby={errors.phone ? "phone-err" : undefined} />
            {errors.phone && <p id="phone-err" className="text-xs text-destructive">{errors.phone}</p>}
          </div>
          {msg && <Alert variant={msg.ok ? "info" : "error"}>{msg.text}</Alert>}
          <Button type="submit" disabled={saving || !dirty}>{saving ? "Saving..." : "Save changes"}</Button>
        </form>
      </CardContent>
    </Card>
  );
}
