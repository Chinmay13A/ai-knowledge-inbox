import { HealthBadge } from './components/HealthBadge'

function App() {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-4">
          <h1 className="text-xl font-semibold">AI Knowledge Inbox</h1>
          <HealthBadge />
        </div>
      </header>

      <main className="mx-auto grid max-w-5xl gap-6 px-4 py-6 md:grid-cols-2">
        <section className="rounded-lg border border-gray-200 bg-white p-4">
          <h2 className="mb-2 font-medium">Add content</h2>
          <p className="text-sm text-gray-500">Coming in Step 7.</p>
        </section>
        <section className="rounded-lg border border-gray-200 bg-white p-4">
          <h2 className="mb-2 font-medium">Ask a question</h2>
          <p className="text-sm text-gray-500">Coming in Step 8.</p>
        </section>
      </main>
    </div>
  )
}

export default App
