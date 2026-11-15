import { useQueryClient } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { Providers } from "@/components/shell/Providers";

function RetryProbe() {
  const retry = useQueryClient().getDefaultOptions().queries?.retry;
  return <output>{String(retry)}</output>;
}

test("should turn query retries off", () => {
  render(
    <Providers>
      <RetryProbe />
    </Providers>,
  );

  expect(screen.getByRole("status")).toHaveTextContent("false");
});
