// Shown to anyone whose joining formalities HR has not finished yet (no
// reporting manager assigned). They can explore the portal but cannot
// submit leave, WFH or regularization requests.
import { useAuth } from '../AuthContext'

export default function OnboardingNotice({ compact }) {
  const { user } = useAuth()
  if (!user?.onboarding_pending) return null
  return (
    <div className="notice" role="status">
      <strong>Awaiting HR onboarding.</strong>{' '}
      {compact
        ? "You haven't been assigned a manager yet, so requests are locked."
        : "Your request has been sent to the HR team to complete your joining formalities. "
          + "Feel free to explore the portal meanwhile. Leave, WFH and regularization requests unlock "
          + "once HR assigns your reporting manager."}
    </div>
  )
}
