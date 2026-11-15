import { Map as AliasedMap } from "maplibre-gl";
import { expect, test, vi } from "vitest";

import { Map as MockMap, Marker as MockMarker } from "@/test/mocks/maplibre-gl";

test("should give the mock when a file imports maplibre-gl", () => {
  expect(AliasedMap).toBe(MockMap);
});

test("should list each created map in Map.instances", () => {
  const map = new MockMap();

  expect(MockMap.instances).toContain(map);
});

test("should start each test with an empty Map.instances", () => {
  expect(MockMap.instances).toEqual([]);
});

test("should keep the options that the map was created with", () => {
  const map = new MockMap({ zoom: 3 });

  expect(map.options).toEqual({ zoom: 3 });
});

test("should return the container element that the options name", () => {
  const container = document.createElement("div");
  const map = new MockMap({ container });

  expect(map.getContainer()).toBe(container);
});

test("should pass the event of fire to a listener added with on", () => {
  const listener = vi.fn();
  const map = new MockMap();
  map.on("moveend", listener);

  map.fire("moveend", { type: "moveend" });

  expect(listener).toHaveBeenCalledWith({ type: "moveend" });
});

test("should stop calling a listener after its subscription is unsubscribed", () => {
  const listener = vi.fn();
  const map = new MockMap();
  map.on("moveend", listener).unsubscribe();

  map.fire("moveend");

  expect(listener).not.toHaveBeenCalled();
});

test("should stop calling a listener that off removed", () => {
  const listener = vi.fn();
  const map = new MockMap();
  map.on("moveend", listener);

  map.off("moveend", listener).fire("moveend");

  expect(listener).not.toHaveBeenCalled();
});

test("should stop calling a layer listener that off removed", () => {
  const listener = vi.fn();
  const map = new MockMap();
  map.on("click", "cells", listener);

  map.off("click", "cells", listener).fire("click", undefined, "cells");

  expect(listener).not.toHaveBeenCalled();
});

test("should keep the map listener and the listener of another layer when off removes a layer listener", () => {
  const listener = vi.fn();
  const map = new MockMap();
  map.on("click", listener);
  map.on("click", "pins", listener);
  map.on("click", "cells", listener);

  map.off("click", "cells", listener).fire("click", undefined, "pins");

  expect(listener).toHaveBeenCalledTimes(2);
});

test("should call a layer listener when fire names its layer", () => {
  const listener = vi.fn();
  const map = new MockMap();
  map.on("click", "cells", listener);

  map.fire("click", undefined, "cells");

  expect(listener).toHaveBeenCalledTimes(1);
});

test("should not call a layer listener when fire names no layer", () => {
  const listener = vi.fn();
  const map = new MockMap();
  map.on("click", "cells", listener);

  map.fire("click");

  expect(listener).not.toHaveBeenCalled();
});

test("should not call a layer listener when fire names another layer", () => {
  const listener = vi.fn();
  const map = new MockMap();
  map.on("click", ["cells", "pins"], listener);

  map.fire("click", undefined, "borders");

  expect(listener).not.toHaveBeenCalled();
});

test("should call a map listener when fire names a layer", () => {
  const listener = vi.fn();
  const map = new MockMap();
  map.on("click", listener);

  map.fire("click", undefined, "cells");

  expect(listener).toHaveBeenCalledTimes(1);
});

test("should run a listener added with once a single time", () => {
  const listener = vi.fn();
  const map = new MockMap();
  map.once("load", listener);

  map.fire("load").fire("load");

  expect(listener).toHaveBeenCalledTimes(1);
});

test("should resolve the promise of once with the fired event when it gets no listener", async () => {
  const map = new MockMap();
  const loaded = map.once("load");

  map.fire("load", { type: "load" });

  await expect(loaded).resolves.toEqual({ type: "load" });
});

test("should return the source that addSource stored", () => {
  const map = new MockMap().addSource("cells");

  expect(map.getSource("cells")).toEqual({ setData: expect.any(Function) });
});

test("should return no source after removeSource removes it", () => {
  const map = new MockMap().addSource("cells").removeSource("cells");

  expect(map.getSource("cells")).toBeUndefined();
});

test("should return the layer that addLayer added", () => {
  const layer = { id: "cells", type: "fill", source: "cells" } as const;
  const map = new MockMap().addLayer(layer);

  expect(map.getLayer("cells")).toBe(layer);
});

test("should return no layer after removeLayer removes it", () => {
  const map = new MockMap()
    .addLayer({ id: "cells", type: "fill", source: "cells" })
    .removeLayer("cells");

  expect(map.getLayer("cells")).toBeUndefined();
});

test("should list each created marker in Marker.instances", () => {
  const marker = new MockMarker();

  expect(MockMarker.instances).toContain(marker);
});

test("should start each test with an empty Marker.instances", () => {
  expect(MockMarker.instances).toEqual([]);
});

test("should return the element that the marker options name", () => {
  const element = document.createElement("button");
  const marker = new MockMarker({ element });

  expect(marker.getElement()).toBe(element);
});

test("should put the marker element into the map container when addTo runs", () => {
  const map = new MockMap();
  const marker = new MockMarker().addTo(map);

  expect(map.getContainer()).toContainElement(marker.getElement());
});

test("should take the marker element out of the map container when remove runs", () => {
  const map = new MockMap();
  const marker = new MockMarker().addTo(map);

  marker.remove();

  expect(map.getContainer()).not.toContainElement(marker.getElement());
});

test("should pass the event of fire to a marker listener added with on", () => {
  const listener = vi.fn();
  const marker = new MockMarker();
  marker.on("dragend", listener);

  marker.fire("dragend", { type: "dragend" });

  expect(listener).toHaveBeenCalledWith({ type: "dragend" });
});

test("should stop calling a marker listener that off removed", () => {
  const listener = vi.fn();
  const marker = new MockMarker();
  marker.on("dragend", listener);

  marker.off("dragend", listener).fire("dragend");

  expect(listener).not.toHaveBeenCalled();
});

test("should stop calling a marker listener after its subscription is unsubscribed", () => {
  const listener = vi.fn();
  const marker = new MockMarker();
  marker.on("dragend", listener).unsubscribe();

  marker.fire("dragend");

  expect(listener).not.toHaveBeenCalled();
});
