import type { QuerySource } from '../api/types'
import { SourceCard } from './SourceCard'

interface SourceListProps {
  sources: QuerySource[]
  highlightedId: number | null
  registerCard: (id: number, element: HTMLLIElement | null) => void
}

export function SourceList({ sources, highlightedId, registerCard }: SourceListProps) {
  const cited = sources.filter((source) => source.cited)
  const others = sources.filter((source) => !source.cited)

  const renderGroup = (group: QuerySource[]) => (
    <ul className="space-y-2">
      {group.map((source) => (
        <SourceCard
          key={source.id}
          source={source}
          highlighted={source.id === highlightedId}
          ref={(element) => registerCard(source.id, element)}
        />
      ))}
    </ul>
  )

  return (
    <div className="space-y-4">
      {cited.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-gray-700">Sources</h3>
          {renderGroup(cited)}
        </div>
      )}
      {others.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-gray-500">Also retrieved (not cited)</h3>
          {renderGroup(others)}
        </div>
      )}
    </div>
  )
}
