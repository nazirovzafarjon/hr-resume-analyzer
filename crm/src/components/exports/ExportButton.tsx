/**
 * ExportButton - Trigger button for opening the export modal
 */

import { Download } from "lucide-react";
import Button from "../ui/Button";

interface ExportButtonProps {
  onClick: () => void;
  disabled?: boolean;
}

export function ExportButton({ onClick, disabled }: ExportButtonProps) {
  return (
    <Button
      variant="secondary"
      icon={<Download size={16} />}
      onClick={onClick}
      disabled={disabled}
    >
      Export Table
    </Button>
  );
}
