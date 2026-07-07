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
// Fix: each callback stashes the intended "home" range in the figure's own
// layout.meta (see callbacks_scattering_2d.py / callbacks_gisaxs.py /
// callbacks_resonant.py) -- meta is inert to Plotly's own zoom/pan/reset
// machinery, so it only ever changes when Dash actually pushes a new
// figure. This watches for the {"xaxis.autorange": true, ...} relayout
// event Plotly sends specifically for Reset Axes / Autoscale, and
// immediately relayouts back to whatever meta currently says.
//
// Critical: the arrays read from meta must be cloned (.slice()) before
// being handed to Plotly.relayout. Plotly.relayout("xaxis.range", arr)
// stores that exact array object as gd.layout.xaxis.range -- so if arr is
// the same array object as gd.layout.meta.homeRangeX, the next zoom's
// in-place mutation of gd.layout.xaxis.range[0]/[1] (that's how Plotly
// applies a box-zoom drag) silently corrupts meta too, since by then
// they're literally the same object in memory. First-hand tested: without
// the clone, this fix works exactly once and then silently breaks on the
// second zoom+reset.
(function () {
    var TARGET_IDS = ["scat-2d-q-graph", "gi-2d-graph", "reson-2d-q-graph"];
    var correcting = {};

    function findGraphDiv(targetId) {
        var wrapper = document.getElementById(targetId);
        return wrapper ? wrapper.querySelector(".js-plotly-plot") : null;
    }

    function attach(targetId) {
        var gd = findGraphDiv(targetId);
        if (!gd || gd.dataset.resetAxesFixBound) return;
        gd.dataset.resetAxesFixBound = "1";

        gd.on("plotly_relayout", function (eventData) {
            if (correcting[targetId]) return;
            var isReset = eventData && (eventData["xaxis.autorange"] === true ||
                                         eventData["yaxis.autorange"] === true);
            if (!isReset) return;

            var meta = gd.layout && gd.layout.meta;
            var homeX = meta && meta.homeRangeX && meta.homeRangeX.slice();
            var homeY = meta && meta.homeRangeY && meta.homeRangeY.slice();
            if (!homeX || !homeY) return;

            correcting[targetId] = true;
            Plotly.relayout(gd, {
                "xaxis.range": homeX,
                "yaxis.range": homeY,
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
