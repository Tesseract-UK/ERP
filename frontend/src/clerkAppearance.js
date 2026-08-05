// Shared Clerk <SignIn>/<SignUp> theming — matches the app's dark palette
// (see styles.css :root) instead of Clerk's default look.
export const clerkAppearance = {
  variables: {
    colorPrimary: '#3395ff',
    colorBackground: '#0c111c',
    colorInputBackground: '#111726',
    colorInputText: '#eef2f9',
    colorText: '#eef2f9',
    colorTextSecondary: '#9aa6bf',
    colorDanger: '#f26d6d',
    colorSuccess: '#2ecc8f',
    borderRadius: '10px',
    fontFamily: 'inherit',
  },
  elements: {
    rootBox: { width: '100%' },
    card: { boxShadow: 'none', border: '1px solid #27314a', width: '100%' },
    headerTitle: { display: 'none' },
    headerSubtitle: { display: 'none' },
    footer: { background: 'transparent' },
    footerActionText: { color: '#9aa6bf' },
    dividerText: { color: '#5f6b85' },
    formFieldInput: { borderColor: '#27314a' },
    socialButtonsBlockButton: { borderColor: '#27314a' },
  },
}
