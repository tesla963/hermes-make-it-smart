/**
 * A stand-in for @hermes/plugin-sdk, just enough to load the plugin outside the
 * host. The real module lives inside the app bundle; the surface used here is
 * three constants and one call.
 */
export const ROUTES_AREA = 'routes'
export const SIDEBAR_NAV_AREA = 'sidebar-nav'
export const KEYBINDS_AREA = 'keybinds'
export const host = {
  openSession: () => true,
  request: async () => true,
  navigate: () => true,
}
export default { host, ROUTES_AREA, SIDEBAR_NAV_AREA, KEYBINDS_AREA }
