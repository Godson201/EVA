import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { ArrowRight } from "lucide-react";

export function FeaturePreview({ eyebrow, title, description, icon: Icon, capabilities }: { eyebrow: string; title: string; description: string; icon: LucideIcon; capabilities: string[] }) {
  return <section className="feature-page"><header className="feature-head"><span className="kicker">{eyebrow}</span><div className="feature-title"><div className="feature-icon large"><Icon/></div><h1>{title}</h1></div><p>{description}</p></header><div className="capability-grid">{capabilities.map((item, index) => <article key={item}><span>0{index + 1}</span><h2>{item}</h2><p>This workflow remains available in classic EVA while its V2 interface is migrated and parity-tested.</p></article>)}</div><div className="migration-callout"><div><strong>Migration in progress</strong><p>The central chat experience is live. This specialized workspace is next in the route-by-route migration.</p></div><Link href={process.env.NEXT_PUBLIC_LEGACY_APP_URL || "http://localhost:3000"}>Open classic EVA <ArrowRight size={16}/></Link></div></section>;
}
