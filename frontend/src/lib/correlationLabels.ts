/** Textual correlation strength — color is secondary to numeric + label. */

export type CorrelationStrength =
  | "perfect"
  | "strong_positive"
  | "moderate_positive"
  | "weak_positive"
  | "negligible"
  | "weak_negative"
  | "moderate_negative"
  | "strong_negative";

export function correlationStrength(value: number | null | undefined, isDiagonal: boolean): CorrelationStrength {
  if (isDiagonal) return "perfect";
  if (value == null || Number.isNaN(value)) return "negligible";
  const v = value;
  const abs = Math.abs(v);
  if (abs >= 0.85) return v >= 0 ? "strong_positive" : "strong_negative";
  if (abs >= 0.55) return v >= 0 ? "moderate_positive" : "moderate_negative";
  if (abs >= 0.25) return v >= 0 ? "weak_positive" : "weak_negative";
  return "negligible";
}

export type CorrelationLabelMessages = {
  perfect: string;
  strongPositive: string;
  moderatePositive: string;
  weakPositive: string;
  negligible: string;
  weakNegative: string;
  moderateNegative: string;
  strongNegative: string;
  cellAria: string;
};

export function correlationStrengthLabel(
  strength: CorrelationStrength,
  messages: CorrelationLabelMessages
): string {
  switch (strength) {
    case "perfect":
      return messages.perfect;
    case "strong_positive":
      return messages.strongPositive;
    case "moderate_positive":
      return messages.moderatePositive;
    case "weak_positive":
      return messages.weakPositive;
    case "weak_negative":
      return messages.weakNegative;
    case "moderate_negative":
      return messages.moderateNegative;
    case "strong_negative":
      return messages.strongNegative;
    default:
      return messages.negligible;
  }
}

export function formatCorrelationCellAria(
  rowSym: string,
  colSym: string,
  value: number | null | undefined,
  isDiagonal: boolean,
  messages: CorrelationLabelMessages
): string {
  const strength = correlationStrength(value, isDiagonal);
  const strengthText = correlationStrengthLabel(strength, messages);
  if (value == null || Number.isNaN(value)) {
    return messages.cellAria
      .replace("{a}", rowSym)
      .replace("{b}", colSym)
      .replace("{value}", "—")
      .replace("{strength}", strengthText);
  }
  return messages.cellAria
    .replace("{a}", rowSym)
    .replace("{b}", colSym)
    .replace("{value}", value.toFixed(2))
    .replace("{strength}", strengthText);
}
