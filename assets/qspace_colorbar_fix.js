// The q-space detector image (scat-2d-q-graph) uses scaleanchor + constrain="domain"
// to keep pixels square. When the data's qx/qy aspect ratio doesn't match the plot
// card's own width:height ratio (e.g. a narrower detector), Plotly shrinks the
// x-axis domain to compensate — but the colorbar's x position is fixed relative to
// the whole plot area, not to that shrunk domain, leaving a gap. Since the card's
// width is responsive (only its height is fixed), the actual domain isn't knowable
// ahead of time in Python, so this polls the rendered figure and nudges the
// colorbar to sit right at the image's real right edge.
(function () {
    var TARGET_ID = "scat-2d-q-graph";
    var COLORBAR_PAD = 0.02;

    function fixColorbar() {
        var gd = document.getElementById(TARGET_ID);
        if (!gd || !gd._fullLayout || !gd._fullData || !gd._fullData.length) return;

        var xaxis = gd._fullLayout.xaxis;
        if (!xaxis || !xaxis.domain) return;

        var targetX = xaxis.domain[1] + COLORBAR_PAD;
        var heatmapTrace = gd._fullData[0];
        var currentX = heatmapTrace && heatmapTrace.colorbar ? heatmapTrace.colorbar.x : null;

        if (currentX !== null && Math.abs(currentX - targetX) < 0.001) return;

        Plotly.restyle(gd, { "colorbar.x": targetX }, [0]);
    }

    setInterval(fixColorbar, 500);
})();
