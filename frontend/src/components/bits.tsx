export function EmptyState({
  title,
  body,
}: {
  title: string;
  body: string;
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-(--border-strong) px-6 py-10 text-center">
      <p className="text-sm font-semibold">{title}</p>
      <p className="max-w-sm text-[13px] text-(--muted)">{body}</p>
    </div>
  );
}
