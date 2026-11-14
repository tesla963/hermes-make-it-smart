/**
 * A stand-in for @hermes/plugin-sdk, just enough to load the plugin outside the
 * host. The real module lives inside the app bundle; the surface used here is
 * five constants and a couple of calls.
 */
export const ROUTES_AREA = 'routes'
export const SIDEBAR_NAV_AREA = 'sidebar-nav'
export const PALETTE_AREA = 'palette'
export const KEYBINDS_AREA = 'keybinds'
export const host = {
  openSession: () => true,
  // El host real escribe window.location.hash; aquí solo se anota el destino.
  navigate: (path) => {
    host.__navigated = path

    return true
  },
  request: async () => true,
}
export default { host, ROUTES_AREA, SIDEBAR_NAV_AREA, PALETTE_AREA, KEYBINDS_AREA }
