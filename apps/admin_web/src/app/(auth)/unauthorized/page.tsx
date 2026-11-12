import { SignOutButton } from "@/components/layout/sign-out-button";

export const metadata = { title: "Access denied" };

export default function UnauthorizedPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Access denied</h1>
      <p className="text-sm text-muted-foreground">
        This account is not authorised to use the admin console. If you think this is a mistake, contact
        a platform administrator.
      </p>
      <SignOutButton variant="outline" />
    </div>
  );
}
