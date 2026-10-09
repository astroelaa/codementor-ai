export function TypingDots({ label = "Mentor is thinking" }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 py-1" role="status" aria-label={label}>
      <span className="typing-dot" />
      <span className="typing-dot" />
      <span className="typing-dot" />
    </span>
  );
}

export function ChatSkeleton() {
  return (
    <div className="flex flex-col gap-2" aria-hidden="true">
      <div className="skeleton h-4 w-11/12" />
      <div className="skeleton h-4 w-3/4" />
    </div>
  );
}

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
