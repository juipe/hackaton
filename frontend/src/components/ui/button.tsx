import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Каждая кнопка в новом языке — капсула. Зелёная подсветка (shadow-green) есть
 * только у первичного действия в его обычных размерах: на мелкой кнопке она
 * читается как грязь, а не как акцент, поэтому размер `sm` её гасит.
 */
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-[17px] [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground shadow-green hover:bg-primary-hover",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-accent hover:text-accent-foreground",
        soft: "bg-accent text-accent-foreground hover:bg-primary hover:text-primary-foreground",
        outline:
          "bg-card text-foreground shadow-flat hover:bg-accent hover:text-accent-foreground",
        ghost: "text-muted-foreground hover:bg-secondary hover:text-foreground",
        muted: "bg-muted text-foreground hover:bg-border",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        success: "bg-primary text-primary-foreground shadow-green hover:bg-primary-hover",
        link: "text-accent-foreground underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-10 px-[18px] text-sm",
        default: "h-[46px] px-[22px] text-[15px]",
        lg: "h-[52px] px-[26px] text-base",
        pill: "h-[42px] px-5 text-[15px]",
        icon: "size-[46px] shrink-0 p-0",
      },
    },
    compoundVariants: [
      // Тень бренда — привилегия крупного первичного действия.
      { variant: "default", size: "sm", className: "shadow-none" },
      { variant: "default", size: "pill", className: "shadow-none" },
      { variant: "default", size: "icon", className: "shadow-none" },
      { variant: "success", size: "sm", className: "shadow-none" },
      { variant: "success", size: "pill", className: "shadow-none" },
      { variant: "success", size: "icon", className: "shadow-none" },
    ],
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, type, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...(asChild ? {} : { type: type ?? "button" })}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
