import { useEffect, useRef } from "react";
import { Toaster } from "sonner";

import { AppRoutes } from "@/routes";

const CLOSE_LABEL = "Закрыть уведомление";

/**
 * sonner 1.7 hardcodes the close button's `aria-label` in English and offers no
 * prop to override it (`containerAriaLabel` covers only the region). The label
 * is therefore rewritten in the DOM as toasts appear, so screen readers never
 * hear English.
 */
function LocalizedToaster() {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = host.current;
    if (!node) return;

    const relabel = () => {
      node.querySelectorAll("[data-close-button]").forEach((button) => {
        if (button.getAttribute("aria-label") !== CLOSE_LABEL) {
          button.setAttribute("aria-label", CLOSE_LABEL);
        }
      });
    };

    relabel();
    const observer = new MutationObserver(relabel);
    observer.observe(node, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={host}>
      <Toaster
        position="top-center"
        richColors
        closeButton
        containerAriaLabel="Уведомления"
      />
    </div>
  );
}

export default function App() {
  return (
    <>
      <AppRoutes />
      <LocalizedToaster />
    </>
  );
}
