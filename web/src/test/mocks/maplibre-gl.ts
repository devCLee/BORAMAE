import type {
  AddLayerObject,
  MapOptions,
  MarkerOptions,
  Subscription,
} from "maplibre-gl";
import { vi } from "vitest";

type Listener = (event?: unknown) => void;
type LayerIds = string | string[];
type ListenerArgs = [Listener] | [LayerIds, Listener];
type OnceArgs = ListenerArgs | [] | [LayerIds];

interface Registration {
  listener: Listener;
  layerIds?: string[];
  isOnce: boolean;
}

const WORLD_BOUNDS = {
  getWest: () => -180,
  getSouth: () => -90,
  getEast: () => 180,
  getNorth: () => 90,
};

/**
 * Stands in for maplibre-gl in Vitest, because jsdom has no WebGL.
 * A test reads the created maps from Map.instances and starts an event with fire.
 * The shared setup file empties Map.instances and Marker.instances before each test.
 * Every method is a spy, so a test can also replace a return value.
 */
export class Map {
  static instances: Map[] = [];

  private registrations: Record<string, Registration[]> = {};
  private sources: Record<string, { setData: ReturnType<typeof vi.fn> }> = {};
  private layers: Record<string, AddLayerObject> = {};
  private canvas = document.createElement("canvas");
  private container: HTMLElement;

  constructor(readonly options: Partial<MapOptions> = {}) {
    const { container } = options;
    this.container =
      (typeof container === "string"
        ? document.getElementById(container)
        : container) ?? document.createElement("div");
    Map.instances.push(this);
  }

  // As in maplibre-gl, on returns a Subscription and not the map, so a call cannot be chained.
  on = vi.fn((type: string, ...args: ListenerArgs): Subscription => {
    const registration = this.register(type, args, false);
    return { unsubscribe: () => this.unregister(type, registration) };
  });

  // As in maplibre-gl, once returns a promise of the event when it gets no listener.
  once = vi.fn((type: string, ...args: OnceArgs): this | Promise<unknown> => {
    if (hasListener(args)) {
      this.register(type, args, true);
      return this;
    }
    return new Promise((resolve) => {
      this.register(type, [...args, resolve], true);
    });
  });

  // As in maplibre-gl, off removes a registration only when both its listener and its layer list match.
  off = vi.fn((type: string, ...args: ListenerArgs) => {
    const { listener, layerIds } = splitArgs(args);
    this.registrations[type] = (this.registrations[type] ?? []).filter(
      (registration) =>
        registration.listener !== listener ||
        !isSameLayerList(registration.layerIds, layerIds),
    );
    return this;
  });

  /**
   * Calls the listeners of the map. With a layer ID, it also calls the listeners of that layer,
   * as a click on a feature of the layer does in maplibre-gl.
   */
  fire(type: string, event?: unknown, layerId?: string) {
    const called = (this.registrations[type] ?? []).filter(
      ({ layerIds }) =>
        layerIds === undefined ||
        (layerId !== undefined && layerIds.includes(layerId)),
    );
    for (const registration of called) {
      if (registration.isOnce) {
        this.unregister(type, registration);
      }
      registration.listener(event);
    }
    return this;
  }

  addSource = vi.fn((id: string) => {
    this.sources[id] = { setData: vi.fn() };
    return this;
  });

  getSource = vi.fn((id: string) => this.sources[id]);

  removeSource = vi.fn((id: string) => {
    delete this.sources[id];
    return this;
  });

  addLayer = vi.fn((layer: AddLayerObject) => {
    this.layers[layer.id] = layer;
    return this;
  });

  getLayer = vi.fn((id: string) => this.layers[id]);

  removeLayer = vi.fn((id: string) => {
    delete this.layers[id];
    return this;
  });

  setLayoutProperty = vi.fn(() => this);

  setPaintProperty = vi.fn(() => this);

  setFilter = vi.fn(() => this);

  setFeatureState = vi.fn(() => this);

  queryRenderedFeatures = vi.fn((): unknown[] => []);

  addControl = vi.fn(() => this);

  removeControl = vi.fn(() => this);

  getCanvas = vi.fn(() => this.canvas);

  isStyleLoaded = vi.fn(() => true);

  loaded = vi.fn(() => true);

  resize = vi.fn(() => this);

  setProjection = vi.fn(() => this);

  easeTo = vi.fn(() => this);

  jumpTo = vi.fn(() => this);

  fitBounds = vi.fn(() => this);

  flyTo = vi.fn(() => this);

  getBounds = vi.fn(() => WORLD_BOUNDS);

  getCenter = vi.fn(() => ({ lng: 0, lat: 0 }));

  getZoom = vi.fn(() => 0);

  getContainer = vi.fn(() => this.container);

  remove = vi.fn();

  private register(type: string, args: ListenerArgs, isOnce: boolean) {
    const registration: Registration = { ...splitArgs(args), isOnce };
    (this.registrations[type] ??= []).push(registration);
    return registration;
  }

  private unregister(type: string, registration: Registration) {
    this.registrations[type] = this.registrations[type].filter(
      (registered) => registered !== registration,
    );
  }
}

export class Marker {
  static instances: Marker[] = [];

  private element: HTMLElement;
  private listeners: Record<string, Listener[]> = {};

  constructor(readonly options: MarkerOptions = {}) {
    this.element = options.element ?? document.createElement("div");
    Marker.instances.push(this);
  }

  on = vi.fn((type: string, listener: Listener): Subscription => {
    (this.listeners[type] ??= []).push(listener);
    return { unsubscribe: () => this.removeListener(type, listener) };
  });

  off = vi.fn((type: string, listener: Listener) => {
    this.removeListener(type, listener);
    return this;
  });

  /** Calls the listeners of the marker, as a drag of the marker does in maplibre-gl. */
  fire(type: string, event?: unknown) {
    for (const listener of this.listeners[type] ?? []) {
      listener(event);
    }
    return this;
  }

  getElement = vi.fn(() => this.element);

  setLngLat = vi.fn(() => this);

  getLngLat = vi.fn(() => ({ lng: 0, lat: 0 }));

  setDraggable = vi.fn(() => this);

  // As in maplibre-gl, the element sits inside the map container, so a test can find and focus it.
  addTo = vi.fn((map: Map) => {
    map.getContainer().appendChild(this.element);
    return this;
  });

  remove = vi.fn(() => {
    this.element.remove();
    return this;
  });

  private removeListener(type: string, listener: Listener) {
    this.listeners[type] = (this.listeners[type] ?? []).filter(
      (registered) => registered !== listener,
    );
  }
}

function hasListener(args: OnceArgs): args is ListenerArgs {
  return typeof args.at(-1) === "function";
}

// As in maplibre-gl, the order of the layer IDs does not count. A map listener has no list.
function isSameLayerList(registered?: string[], requested?: string[]) {
  if (registered === undefined || requested === undefined) {
    return registered === requested;
  }
  return (
    registered.length === requested.length &&
    registered.every((layerId) => requested.includes(layerId))
  );
}

// maplibre-gl takes one layer ID or a list of them before the listener.
function splitArgs(args: ListenerArgs) {
  return args.length === 1
    ? { listener: args[0] }
    : { layerIds: [args[0]].flat(), listener: args[1] };
}

export const setWorkerUrl = vi.fn();
