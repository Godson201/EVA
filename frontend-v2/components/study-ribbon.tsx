"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, FileText, Headphones } from "lucide-react";
import { cn } from "@/lib/utils";

const tools = [
  {
    href: "/study",
    label: "Study",
    description: "Learn and create",
    icon: BookOpen,
  },
  {
    href: "/documents",
    label: "Documents",
    description: "Find and read files",
    icon: FileText,
  },
  {
    href: "/voice",
    label: "Audio",
    description: "Voices and listening",
    icon: Headphones,
  },
];

export function StudyRibbon() {
  const pathname = usePathname();
  return (
    <nav className="study-ribbon" aria-label="Study tools">
      {tools.map(({ href, label, description, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          className={cn("study-ribbon-link", pathname === href && "active")}
        >
          <Icon />
          <span>
            <strong>{label}</strong>
            <small>{description}</small>
          </span>
        </Link>
      ))}
    </nav>
  );
}
