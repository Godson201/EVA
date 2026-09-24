import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "EVA — Bilingual AI",
    short_name: "EVA",
    description: "English–Kinyarwanda conversations, study and translation.",
    start_url: "/",
    display: "standalone",
    background_color: "#f4f1e9",
    theme_color: "#17211d",
    orientation: "portrait-primary",
  };
}
