"use client";

import { cn } from "cn";
import { Slider as SliderPrimitive } from "radix-ui";
import { type ComponentProps, useRef, useState } from "react";

type LabeledSliderProps = ComponentProps<typeof SliderPrimitive.Root> & {
  /** One accessible name for each thumb, in the order of the values. */
  thumbLabels: string[];
};

/**
 * The slider of components/ui/slider.tsx with a name on each thumb. That wrapper
 * names no thumb, and Radix then reads "Minimum" and "Maximum" in English.
 */
export function LabeledSlider({
  thumbLabels,
  className,
  ...props
}: LabeledSliderProps) {
  return (
    <SliderPrimitive.Root
      className={cn(
        "relative flex min-h-11 touch-none items-center select-none data-disabled:opacity-50",
        className,
      )}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-1 grow overflow-hidden rounded-full bg-muted">
        <SliderPrimitive.Range className="absolute h-full bg-primary" />
      </SliderPrimitive.Track>
      {thumbLabels.map((label) => (
        <SliderPrimitive.Thumb
          key={label}
          aria-label={label}
          className="relative block size-4 shrink-0 rounded-full border border-ring bg-background ring-ring/50 transition-[box-shadow] select-none after:absolute after:-inset-3.5 hover:ring-3 focus-visible:ring-3 focus-visible:outline-hidden"
        />
      ))}
    </SliderPrimitive.Root>
  );
}

/**
 * The values a slider shows: where the pointer drags them, else the stored ones,
 * which only a commit changes. Spread dragProps on the slider. Radix reports a key
 * press as a change after its commit, so a change outside a drag is dropped: the
 * store holds it already.
 */
export function useDragValues(stored: number[]) {
  const [dragged, setDragged] = useState<number[] | null>(null);
  const isDragging = useRef(false);
  const shown = dragged ?? stored;
  return {
    shown,
    dragProps: {
      value: shown,
      onPointerDown: () => {
        isDragging.current = true;
      },
      // Runs before the commit of Radix, which reads the values of this render.
      onPointerUp: () => {
        isDragging.current = false;
        setDragged(null);
      },
      onValueChange: (values: number[]) => {
        if (isDragging.current) {
          setDragged(values);
        }
      },
    },
  };
}
