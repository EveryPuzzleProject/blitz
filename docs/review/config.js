// Settings for the public review site. `blitz site-build` copies this to docs/review/config.js
// if that doesn't exist yet; edit that copy. These values are public by design: the anon key only
// allows what the database's row-level security allows. Never put the service key here.
window.BLITZ_SITE = {
  name: "blitz",
  googleClientId: "",  // Google Cloud > Credentials > your OAuth client ID (public): Google's own button, so it shows this site
  providers: ["google", "github", "discord"],                      // sign-in buttons: those enabled in Supabase > Sign In / Providers
  supabaseUrl: "https://gvvgqyyutekmxkttxhzd.supabase.co",   // Supabase: Project Settings > API > Project URL
  supabaseAnonKey: "sb_publishable_B_NPnAXFett7uk33ex1_mQ_ulAjxrMA",                   // Supabase: Project Settings > API > anon public key
  filesBase: "https://pub-52ac4a15c4ba43fe8e4af5a496733fb5.r2.dev",            // R2: the bucket's public URL (r2.dev or a custom domain)
};
