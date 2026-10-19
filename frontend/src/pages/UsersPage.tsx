import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Plus } from "@/components/icons";
import { authApi } from "@/api/endpoints";
import { queryClient } from "@/lib/queryClient";
import type { ApiError } from "@/lib/api";
import type { Role, User } from "@/types/api";
import { formatDate } from "@/lib/format";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/components/Toast";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Input, Label, Select } from "@/components/ui/Field";
import { Table, Td, Th, Tr } from "@/components/ui/Table";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";

const ROLE_OPTIONS = [
  { value: "viewer", label: "Viewer" },
  { value: "reviewer", label: "Reviewer" },
  { value: "admin", label: "Admin" },
];

export function UsersPage() {
  useDocumentTitle("Users");
  const { user: me } = useAuth();
  const { notify } = useToast();
  const [showCreate, setShowCreate] = useState(false);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["users"],
    queryFn: authApi.listUsers,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["users"] });

  const update = useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string;
      body: Partial<Pick<User, "full_name" | "email" | "role" | "is_active">>;
    }) => authApi.updateUser(id, body),
    onSuccess: () => {
      notify("success", "User updated");
      invalidate();
    },
    onError: (e) => notify("error", (e as unknown as ApiError)?.message ?? "Update failed"),
  });

  const resetPw = useMutation({
    mutationFn: ({ id, pw }: { id: string; pw: string }) =>
      authApi.resetPassword(id, pw),
    onSuccess: () => notify("success", "Password reset"),
    onError: (e) => notify("error", (e as unknown as ApiError)?.message ?? "Reset failed"),
  });

  return (
    <div>
      <PageHeader
        title="Users"
        description="Manage console accounts and roles."
        actions={
          <Button size="sm" onClick={() => setShowCreate((s) => !s)}>
            Add user
          </Button>
        }
      />

      {showCreate && (
        <CreateUserForm
          onDone={() => {
            setShowCreate(false);
            invalidate();
          }}
        />
      )}

      <Card>
        {isLoading ? (
          <div className="p-4">
            <Skeleton className="h-40 w-full" />
          </div>
        ) : isError ? (
          <ErrorState onRetry={() => refetch()} />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>User</Th>
                <Th className="w-36">Role</Th>
                <Th className="w-24">Status</Th>
                <Th className="w-28">Created</Th>
                <Th className="w-px">Actions</Th>
              </tr>
            </thead>
            <tbody>
              {data?.map((u) => {
                const isSelf = u.id === me?.id;
                const isBootstrap = u.is_bootstrap;
                return (
                  <Tr key={u.id}>
                    <Td>
                      <div className="font-medium text-ink">{u.full_name}</div>
                      <div className="font-mono text-[12px] text-ink-subtle">
                        {u.email}
                        {isSelf && " · you"}
                      </div>
                    </Td>
                    <Td>
                      <Select
                        options={ROLE_OPTIONS}
                        value={u.role}
                        disabled={isBootstrap || update.isPending}
                        onChange={(e) =>
                          update.mutate({
                            id: u.id,
                            body: { role: e.target.value as Role },
                          })
                        }
                        className="h-8 w-32 text-[13px]"
                      />
                    </Td>
                    <Td>
                      <Badge tone={u.is_active ? "ok" : "neutral"}>
                        {u.is_active ? "Active" : "Disabled"}
                      </Badge>
                    </Td>
                    <Td className="text-[12px] text-ink-muted">
                      {formatDate(u.created_at)}
                    </Td>
                    <Td>
                      <div className="flex justify-end gap-1.5">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            const pw = window.prompt(
                              `New password for ${u.email} (min 8 chars):`,
                            );
                            if (pw && pw.length >= 8)
                              resetPw.mutate({ id: u.id, pw });
                            else if (pw)
                              notify("error", "Password must be at least 8 characters");
                          }}
                        >
                          Reset password
                        </Button>
                        {!isBootstrap && (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={update.isPending}
                            onClick={() =>
                              update.mutate({
                                id: u.id,
                                body: { is_active: !u.is_active },
                              })
                            }
                          >
                            {u.is_active ? "Disable" : "Enable"}
                          </Button>
                        )}
                      </div>
                    </Td>
                  </Tr>
                );
              })}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function CreateUserForm({ onDone }: { onDone: () => void }) {
  const { notify } = useToast();
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    role: "viewer" as Role,
    password: "",
  });

  const create = useMutation({
    mutationFn: () =>
      authApi.createUser({
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        role: form.role,
        password: form.password,
      }),
    onSuccess: (u) => {
      notify("success", `Created ${u.email}`);
      onDone();
    },
    onError: (e) =>
      notify("error", (e as unknown as ApiError)?.message ?? "Create failed"),
  });

  return (
    <Card className="mb-3 p-4">
      <form
        className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <div>
          <Label htmlFor="nu-name">Full name</Label>
          <Input
            id="nu-name"
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            required
          />
        </div>
        <div>
          <Label htmlFor="nu-email">Email</Label>
          <Input
            id="nu-email"
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            required
          />
        </div>
        <div>
          <Label htmlFor="nu-role">Role</Label>
          <Select
            id="nu-role"
            options={ROLE_OPTIONS}
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value as Role })}
          />
        </div>
        <div>
          <Label htmlFor="nu-pw">Password</Label>
          <Input
            id="nu-pw"
            type="text"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            required
            minLength={8}
            placeholder="min 8 characters"
          />
        </div>
        <div className="flex items-end gap-2">
          <Button type="submit" size="sm" loading={create.isPending}>
            <Plus className="h-3.5 w-3.5" />
            Create
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={onDone}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}
