from __future__ import annotations

import matplotlib
import matplotlib.pyplot as plt

from alumina_sol_extractor.manuscript_figures.style import configure_style


def test_manuscript_figures_use_agg_backend_and_white_canvas() -> None:
    assert matplotlib.get_backend().lower() == "agg"

    configure_style()
    fig, ax = plt.subplots()
    try:
        assert fig.get_facecolor() == (1.0, 1.0, 1.0, 1.0)
        assert ax.get_facecolor() == (1.0, 1.0, 1.0, 1.0)
        assert plt.rcParams["svg.fonttype"] == "none"
        assert plt.rcParams["pdf.fonttype"] == 42
    finally:
        plt.close(fig)
