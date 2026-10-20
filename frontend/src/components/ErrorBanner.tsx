interface ErrorBannerProps {
  message: string
  onRetry?: () => void
}

export function ErrorBanner({ message, onRetry }: ErrorBannerProps) {
  return (
    <div role="alert" className="flex items-start justify-between gap-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
      <span>{message}</span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="shrink-0 rounded border border-red-300 px-2 py-0.5 text-xs font-medium hover:bg-red-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
        >
          Retry
        </button>
      )}
    </div>
  )
}
