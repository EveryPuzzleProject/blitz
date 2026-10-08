// Settings for the public review site. `blitz site-build` copies this to docs/review/config.js
// if that doesn't exist yet; edit that copy. These values are public by design: the anon key only
// allows what the database's row-level security allows. Never put the service key here.
window.BLITZ_SITE = {
  name: "blitz",
  googleClientId: "",  // optional: Google's own sign-in button (Google then names this site, not Supabase)
  providers: ["google", "github"],                      // sign-in buttons: those enabled in Supabase > Sign In / Providers
  supabaseUrl: "https://YOUR-PROJECT.supabase.co",   // Supabase: Project Settings > API > Project URL
  supabaseAnonKey: "YOUR-ANON-KEY",                   // Supabase: Project Settings > API > anon public key
  filesBase: "https://YOUR-R2-PUBLIC-URL",            // R2: the bucket's public URL (r2.dev or a custom domain)
};
