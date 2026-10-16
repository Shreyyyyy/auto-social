"use client";
import Link from "next/link";
import {use} from "react";
import ReelView from "@/components/ReelView";

export default function ReelPage({params}: {params: Promise<{id: string}>}) {
  const {id} = use(params);
  return (
    <div className="space-y-4">
      <Link href="/library" className="text-sm text-zinc-400 hover:text-white">← Library</Link>
      <ReelView id={id} />
    </div>
  );
}
