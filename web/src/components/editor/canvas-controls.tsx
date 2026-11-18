"use client";

import { ControlButton, Controls, useReactFlow, useStore } from "@xyflow/react";
import { Scan, WandSparkles, ZoomIn, ZoomOut } from "lucide-react";
import type { ReactNode } from "react";

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

import { tidyCanvas } from "./actions";

const FIT = { maxZoom: 1, padding: 0.3, duration: 200 };

function Control({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={<ControlButton aria-label={label} onClick={onClick} disabled={disabled} />}
      >
        {children}
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

export function CanvasControls() {
  const { zoomIn, zoomOut, fitView } = useReactFlow();
  const zoom = useStore((s) => s.transform[2]);
  const minZoom = useStore((s) => s.minZoom);
  const maxZoom = useStore((s) => s.maxZoom);

  return (
    <TooltipProvider>
      <Controls showZoom={false} showFitView={false} showInteractive={false}>
        <Control label="Zoom in" onClick={() => void zoomIn({ duration: 150 })} disabled={zoom >= maxZoom}>
          <ZoomIn />
        </Control>
        <Control label="Zoom out" onClick={() => void zoomOut({ duration: 150 })} disabled={zoom <= minZoom}>
          <ZoomOut />
        </Control>
        <Control label="Fit to screen" onClick={() => void fitView(FIT)}>
          <Scan />
        </Control>
        <Control
          label="Auto layout"
          onClick={() => {
            tidyCanvas();
            void fitView(FIT);
          }}
        >
          <WandSparkles />
        </Control>
      </Controls>
    </TooltipProvider>
  );
}
