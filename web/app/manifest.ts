import type {MetadataRoute} from "next";

// "Add to Home Screen" on a phone opens Katha full-screen, like an app.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Katha — topic in, reels everywhere", short_name: "Katha", start_url: "/", display: "standalone",
    background_color: "#05040b", theme_color: "#05040b",
    icons: [{src: "/icon.svg", type: "image/svg+xml", sizes: "any"}, {src: "/icon-512.png", type: "image/png", sizes: "512x512"}],
  };
}
