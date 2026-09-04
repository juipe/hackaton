import { type ClassValue, clsx } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/**
 * tailwind-merge ничего не знает о нашей шкале из `tailwind.config.js`, поэтому
 * без этого расширения `rounded-md rounded-card` или `shadow-green shadow-none`
 * доезжали до DOM обоими классами, а побеждал тот, чьё правило стоит ниже в
 * собранном CSS (правила сортируются по алфавиту). Перечисляем кастомные ключи
 * радиусов (§2.2) и теней (§2.3), чтобы переопределение решалось порядком
 * аргументов, как и ожидается от `cn`.
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      rounded: [{ rounded: ["card", "panel", "row", "tile", "field", "badge", "chip"] }],
      shadow: [
        {
          shadow: [
            "flat",
            "card",
            "panel",
            "panelHover",
            "nav",
            "modal",
            "green",
            "greenSm",
          ],
        },
      ],
    },
  },
});

/** Conditional class names with Tailwind conflict resolution. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** First letters of a name, for avatar fallbacks. */
export function initials(name: string): string {
  return (name ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

/**
 * Stable, pleasant avatar colour derived from an id.
 *
 * Пять пар из макета. Единственное место в проекте (вместе с палитрой графиков),
 * где HEX разрешён напрямую: это не роли интерфейса, а фиксированный набор
 * оттенков, и заводить под каждый из десяти по токену было бы шумом.
 */
export function avatarTone(seed: string): string {
  const tones = [
    "bg-[#E8F6EA] text-[#14732A]", // зелёный
    "bg-[#FEF3DA] text-[#96631E]", // янтарный
    "bg-[#E7F1FB] text-[#1E6796]", // синий
    "bg-[#F3E7F0] text-[#8A4A78]", // сливовый
    "bg-[#EAF0DC] text-[#5F7024]", // оливковый
  ];
  let hash = 0;
  for (let index = 0; index < seed.length; index += 1) {
    hash = (hash * 31 + seed.charCodeAt(index)) % 100000;
  }
  return tones[hash % tones.length];
}
