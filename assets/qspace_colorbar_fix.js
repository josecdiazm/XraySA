// The q-space detector image (scat-2d-q-graph) uses scaleanchor + constrain="domain"
// to keep pixels square. When the data's qx/qy aspect ratio doesn't match the plot
// card's own width:height ratio, Plotly shrinks whichever axis domain is needed to
// compensate — the x-axis for a "portrait" detector orientation, or the y-axis for
// a "landscape" one (e.g. after rotating a thin detector 90° with Rot3). Either way,
// the colorbar's x/y/len stay fixed relative to the whole plot area, not to that
// shrunk domain, leaving a gap. Since the card's width is responsive, the actual
// domain isn't knowable ahead of time in Python, so this polls the rendered figure
// and matches the colorbar's position and length to the image's real domain.
(function () {
    var TARGET_ID = "scat-2d-q-graph";
    var PAD = 0.02;
    var LEN_FRACTION = 0.95;

    function fixColorbar() {
        // dcc.Graph puts the id we gave it on an *outer wrapper* div; Plotly.js
        // actually draws into an unlabeled inner div (tagged "js-plotly-plot")
        // nested inside it. _fullLayout/_fullData only ever exist on that inner
        // one, so we have to descend into it explicitly.
        var wrapper = document.getElementById(TARGET_ID);
        var gd = wrapper ? wrapper.querySelector(".js-plotly-plot") : null;
        if (!gd || !gd._fullLayout || !gd._fullData || !gd._fullData.length) return;

        var xaxis = gd._fullLayout.xaxis;
        var yaxis = gd._fullLayout.yaxis;
        if (!xaxis || !xaxis.domain || !yaxis || !yaxis.domain) return;

        var targetX = xaxis.domain[1] + PAD;
        var targetY = (yaxis.domain[0] + yaxis.domain[1]) / 2;
        var targetLen = (yaxis.domain[1] - yaxis.domain[0]) * LEN_FRACTION;

        var heatmapTrace = gd._fullData[0];
        var cb = heatmapTrace && heatmapTrace.colorbar;
        if (!cb) return;

        var changed =
            Math.abs((cb.x || 0) - targetX) > 0.001 ||
            Math.abs((cb.y || 0) - targetY) > 0.001 ||
            Math.abs((cb.len || 0) - targetLen) > 0.001;

        if (!changed) return;

        Plotly.restyle(
            gd,
            {
                "colorbar.x": targetX,
                "colorbar.y": targetY,
                "colorbar.len": targetLen,
                "colorbar.yanchor": "middle",
            },
            [0]
        );
    }

    setInterval(fixColorbar, 500);
})();
