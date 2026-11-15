"use client";

import { Plus } from "lucide-react";

import { TemplatePicker } from "@/components/templates/template-picker";
import { Button } from "@/components/ui/button";

export function NewFlowButton() {
  return (
    <TemplatePicker
      trigger={
        <Button className="h-10">
          <Plus aria-hidden /> New flow
        </Button>
      }
    />
  );
}

export function StartFromTemplateButton() {
  return <TemplatePicker trigger={<Button className="h-10">Start from a template</Button>} />;
}
