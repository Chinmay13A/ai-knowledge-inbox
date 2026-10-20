import { AskPanel } from './components/AskPanel'
import { HealthBadge } from './components/HealthBadge'
import { IngestForm } from './components/IngestForm'
import { ItemList } from './components/ItemList'
import { useItems } from './hooks/useItems'

function App() {
  const items = useItems()

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-4">
          <h1 className="text-xl font-semibold">AI Knowledge Inbox</h1>
          <HealthBadge />
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl gap-6 px-4 py-6 lg:grid-cols-2">
        <div className="min-w-0 space-y-6">
          <IngestForm onCreated={items.addItem} />
          <ItemList {...items} />
        </div>

        <AskPanel readyCount={items.items.filter((item) => item.status === 'ready').length} />
      </main>
    </div>
  )
}

export default App
