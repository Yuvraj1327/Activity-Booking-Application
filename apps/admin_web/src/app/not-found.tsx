import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-3 p-10 text-center">
      <h2 className="text-lg font-semibold">Page not found</h2>
      <Link href="/dashboard" className="text-sm text-primary underline">
        Back to dashboard
      </Link>
    </div>
  );
}
