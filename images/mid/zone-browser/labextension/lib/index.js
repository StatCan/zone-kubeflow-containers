/**
 * zone-browser-autoopen
 *
 * Holds a websocket to the zone-browser viewer bridge ({base}/zone-browser/
 * events, via jupyter-server-proxy). When an in-pod sign-in starts (az login,
 * azure-identity, R AzureAuth -> zone-browser CLI -> bridge /open), the
 * bridge broadcasts {"type": "open"} and this plugin opens (or focuses) the
 * Zone Browser as a tab in the main area, next to the user's current tab --
 * no printed links, nothing opens in the user's own browser.
 */
const { IFrame, MainAreaWidget } = require('@jupyterlab/apputils');
const { PageConfig, URLExt } = require('@jupyterlab/coreutils');

const plugin = {
  id: 'zone-browser-autoopen:plugin',
  autoStart: true,
  activate: app => {
    const viewerUrl = URLExt.join(PageConfig.getBaseUrl(), 'zone-browser') + '/';
    const eventsUrl = viewerUrl.replace(/^http/, 'ws') + 'events';
    let widget = null;

    const openTab = () => {
      void app.restored.then(() => {
        if (!widget || widget.isDisposed) {
          const content = new IFrame({
            sandbox: [
              'allow-same-origin',
              'allow-scripts',
              'allow-forms',
              'allow-modals',
              'allow-popups',
              'allow-downloads'
            ]
          });
          content.url = viewerUrl;
          widget = new MainAreaWidget({ content });
          widget.id = 'zone-browser-autoopen';
          widget.title.label = 'Zone Browser';
          widget.title.caption = 'Secure browser running inside your workspace';
          widget.title.closable = true;
          app.shell.add(widget, 'main', { mode: 'tab-after' });
        }
        app.shell.activateById(widget.id);
      });
    };

    // The bridge process may not exist yet (jupyter-server-proxy starts it on
    // first request) or may be restarted; reconnect with backoff forever.
    let retryMs = 2000;
    const connect = () => {
      let ws;
      try {
        ws = new WebSocket(eventsUrl);
      } catch (err) {
        scheduleReconnect();
        return;
      }
      ws.onopen = () => {
        retryMs = 2000;
      };
      ws.onmessage = ev => {
        try {
          if (JSON.parse(ev.data).type === 'open') {
            openTab();
          }
        } catch (err) {
          /* not for us */
        }
      };
      ws.onclose = () => scheduleReconnect();
      ws.onerror = () => {
        try {
          ws.close();
        } catch (err) {
          /* already closed */
        }
      };
    };
    const scheduleReconnect = () => {
      setTimeout(connect, retryMs);
      retryMs = Math.min(retryMs * 2, 60000);
    };
    connect();
  }
};

module.exports = plugin;
