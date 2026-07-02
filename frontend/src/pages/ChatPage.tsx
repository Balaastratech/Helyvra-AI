import { PatientPicker } from '@/components/PatientPicker'
import { ChatPane } from '@/components/ChatPane'
import { DropZone } from '@/components/DropZone'
import { InspectorDrawer } from '@/components/InspectorDrawer'
import { useUi } from '@/store'

/**
 * Chat-first landing page: conversational agent + global drop-zone.
 * The primary user experience — ask questions, upload documents.
 */
export function ChatPage() {
  const patientId = useUi((s) => s.patientId)

  if (!patientId) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-6 p-8">
        <div className="w-full max-w-xl">
          <DropZone />
          <p className="mt-3 text-center text-xs text-text-muted">
            Or select an existing patient below
          </p>
        </div>
        <PatientPicker />
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0">
      {/* Main column: drop-zone + chat */}
      <div className="flex flex-1 min-h-0 flex-col">
        <div className="shrink-0 border-b border-border px-4 py-3">
          <DropZone />
        </div>
        <div className="min-h-0 flex-1">
          <ChatPane />
        </div>
      </div>
      {/* Inspector drawer (collapsible, off by default) */}
      <InspectorDrawer />
    </div>
  )
}
