// Several 2-D q-space plots (Scattering 2D & 1D's scat-2d-q-graph,
// GI-SWAXS's gi-2d-graph, Resonant Scattering's reson-2d-q-graph) pin their
// axes to the detector's real data extent (xaxis.range/yaxis.range with
// autorange:false) so a wedge overlay drawn past real data doesn't stretch
// the initial view. Plotly's own Reset Axes / Autoscale modebar button
// ignores that fixed range, though -- it always recomputes a "fit
// everything currently on the plot" view, including any wedge/overlay
// trace that extends past the detector image, so clicking it can zoom out
// further than the detector itself.
//
// This restores each plot's own "home" range (whatever Dash most recently
// set) every time that button's reset is detected, by watching for the
// {"xaxis.autorange": true, "yaxis.autorange": true} relayout event Plotly
// sends specifically for Reset Axes / Autoscale, and immediately relayout-
// ing back to the last range Dash actually rendered.
(function () {
    var TARGET_IDS = ["scat-2d-q-graph", "gi-2d-graph", "reson-2d-q-graph"];
    var homeRanges = {};   // keyed by target id -- each plot tracks its own
    var correcting = {};

    function findGraphDiv(targetId) {
        var wrapper = document.getElementById(targetId);
        return wrapper ? wrapper.querySelector(".js-plotly-plot") : null;
    }

    function attach(targetId) {
        var gd = findGraphDiv(targetId);
        if (!gd || gd.dataset.resetAxesFixBound) return;
        gd.dataset.resetAxesFixBound = "1";

        // Every genuine data-driven redraw (a fresh figure pushed by Dash)
        // fires plotly_afterplot; plain user pan/zoom only fires
        // plotly_relayout, not afterplot -- so this only re-baselines
        // "home" when the server actually sent new axis bounds.
        gd.on("plotly_afterplot", function () {
            if (correcting[targetId]) return;
            var xr = gd.layout && gd.layout.xaxis && gd.layout.xaxis.range;
            var yr = gd.layout && gd.layout.yaxis && gd.layout.yaxis.range;
            if (xr && yr) {
                homeRanges[targetId] = { x: xr.slice(), y: yr.slice() };
            }
        });

        gd.on("plotly_relayout", function (eventData) {
            var home = homeRanges[targetId];
            if (correcting[targetId] || !home) return;
            var isReset = eventData && (eventData["xaxis.autorange"] === true ||
                                         eventData["yaxis.autorange"] === true);
            if (!isReset) return;

            correcting[targetId] = true;
            Plotly.relayout(gd, {
                "xaxis.range": home.x,
                "yaxis.range": home.y,
                "xaxis.autorange": false,
                "yaxis.autorange": false,
            }).then(function () { correcting[targetId] = false; })
              .catch(function () { correcting[targetId] = false; });
        });
    }

    setInterval(function () {
        TARGET_IDS.forEach(attach);
    }, 500);
})();
