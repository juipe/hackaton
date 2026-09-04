import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import * as SheetPrimitive from "@radix-ui/react-dialog";
import { cva } from "class-variance-authority";
import { X } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";
const Sheet = SheetPrimitive.Root;
const SheetTrigger = SheetPrimitive.Trigger;
const SheetClose = SheetPrimitive.Close;
const SheetPortal = SheetPrimitive.Portal;
const SheetOverlay = React.forwardRef(({ className, ...props }, ref) => (_jsx(SheetPrimitive.Overlay, { ref: ref, className: cn("fixed inset-0 z-50 bg-foreground/40 backdrop-blur-[1px] data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0", className), ...props })));
SheetOverlay.displayName = SheetPrimitive.Overlay.displayName;
const sheetVariants = cva("fixed z-50 flex flex-col gap-4 overflow-y-auto overscroll-contain bg-card p-5 shadow-modal transition ease-in-out data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:duration-200 data-[state=open]:duration-300 sm:p-6", {
    variants: {
        side: {
            top: "inset-x-0 top-0 max-h-[90vh] border-b border-border data-[state=closed]:slide-out-to-top data-[state=open]:slide-in-from-top",
            bottom: "inset-x-0 bottom-0 max-h-[90vh] rounded-t-xl border-t border-border data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom",
            left: "inset-y-0 left-0 h-full max-h-screen w-[85%] max-w-sm border-r border-border data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left",
            right: "inset-y-0 right-0 h-full max-h-screen w-[85%] max-w-sm border-l border-border data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right",
        },
    },
    defaultVariants: {
        side: "right",
    },
});
const SheetContent = React.forwardRef(({ side = "right", className, children, showCloseButton = true, ...props }, ref) => (_jsxs(SheetPortal, { children: [_jsx(SheetOverlay, {}), _jsxs(SheetPrimitive.Content, { ref: ref, className: cn(sheetVariants({ side }), className), ...props, children: [children, showCloseButton ? (_jsxs(SheetPrimitive.Close, { className: "absolute right-4 top-4 flex size-11 items-center justify-center rounded-md text-muted-foreground opacity-80 transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none", children: [_jsx(X, { className: "size-4", "aria-hidden": "true" }), _jsx("span", { className: "sr-only", children: "\u0417\u0430\u043A\u0440\u044B\u0442\u044C" })] })) : null] })] })));
SheetContent.displayName = SheetPrimitive.Content.displayName;
function SheetHeader({ className, ...props }) {
    return (_jsx("div", { className: cn("flex flex-col space-y-1.5 pr-8 text-left", className), ...props }));
}
SheetHeader.displayName = "SheetHeader";
function SheetFooter({ className, ...props }) {
    return (_jsx("div", { className: cn("mt-auto flex flex-col-reverse gap-2 sm:flex-row sm:justify-end", className), ...props }));
}
SheetFooter.displayName = "SheetFooter";
const SheetTitle = React.forwardRef(({ className, ...props }, ref) => (_jsx(SheetPrimitive.Title, { ref: ref, className: cn("text-base font-semibold tracking-tight text-foreground", className), ...props })));
SheetTitle.displayName = SheetPrimitive.Title.displayName;
const SheetDescription = React.forwardRef(({ className, ...props }, ref) => (_jsx(SheetPrimitive.Description, { ref: ref, className: cn("text-sm text-muted-foreground", className), ...props })));
SheetDescription.displayName = SheetPrimitive.Description.displayName;
export { Sheet, SheetTrigger, SheetClose, SheetPortal, SheetOverlay, SheetContent, SheetHeader, SheetFooter, SheetTitle, SheetDescription, };
