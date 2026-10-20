CONTAINER_STYLES = """
    QWidget#toolbar {
        background: transparent;
        border: none;
        border-bottom: 1px solid #29343a;
        border-radius: 0px;
    }

    QScrollArea {
        background: transparent;
        border: none;
    }

    QGroupBox {
        color: #f2f2ef;
        background: #1a2023;
        border: 1px solid #303a3e;
        border-radius: 7px;
        font-weight: 900;
        margin-top: 18px;
        padding-top: 12px;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        padding: 0px 7px;
        color: #ffffff;
        background: #1a2023;
        border: none;
        border-radius: 3px;
        font-size: 18px;
    }

    QGroupBox#innerPanel::title {
        font-size: 14px;
    }

    QGroupBox#innerPanel {
        background: rgba(9, 13, 14, 170);
        border-color: rgba(77, 105, 104, 90);
        margin-top: 15px;
        padding-top: 10px;
    }

    QFrame#compactPanel {
        background: rgba(9, 13, 14, 170);
        border: 1px solid rgba(77, 105, 104, 90);
        border-radius: 6px;
    }

    QFrame#statusCard {
        background: rgba(9, 13, 14, 170);
        border: 1px solid rgba(77, 105, 104, 90);
        border-radius: 6px;
    }

    QFrame#statusCard[state="ok"] {
        background: #101715;
        border-color: #2e7d66;
    }

    QFrame#statusCard[state="error"] {
        background: #171211;
        border-color: #7e3b35;
    }

    QFrame#statusCard[state="unchecked"] {
        background: #1c2225;
        border-color: #394348;
    }

    QFrame#summaryCard {
        background: #1a2023;
        border: 1px solid #303a3e;
        border-radius: 7px;
        min-height: 68px;
    }

    QFrame#summaryCard[state="running"] { border-left: 3px solid #3fa47e; }
    QFrame#summaryCard[state="waiting"],
    QFrame#summaryCard[state="starting"],
    QFrame#summaryCard[state="stopping"] { border-left: 3px solid #d49a3a; }
    QFrame#summaryCard[state="failed"] { border-left: 3px solid #b84a43; }
    QFrame#summaryCard[state="stopped"],
    QFrame#summaryCard[state="unchecked"] { border-left: 3px solid #667278; }

    QFrame#destinationCard {
        background: #141a1d;
        border: 1px solid #334047;
        border-radius: 6px;
    }

    QFrame#trafficCard {
        background: #141a1d;
        border: 1px solid #334047;
        border-radius: 7px;
    }

    QFrame#sourceCard {
        background: rgba(6, 9, 10, 190);
        border: 1px solid rgba(105, 128, 127, 105);
        border-radius: 6px;
    }

    QFrame#sourceCard[active="true"] {
        background: rgba(11, 17, 18, 205);
        border-color: rgba(178, 205, 202, 130);
    }

    QFrame#sourceCard[active="false"] {
        background: #0b0d0d;
        border-color: #262c2c;
    }

    QFrame#operateRow {
        background: #141c20;
        border: 1px solid #314047;
        border-radius: 6px;
    }

    QFrame#operatePanel {
        background: #152129;
        border: 1px solid #1b2932;
        border-radius: 8px;
    }

    QFrame#operateListRow {
        background: transparent;
        border: none;
    }

    QFrame#operateSeparator {
        color: #33434d;
        background: #33434d;
        border: none;
        min-height: 1px;
        max-height: 1px;
    }

    QFrame#throughputBar {
        background: transparent;
        border-top: 1px solid #2d393e;
        border-bottom: 1px solid #202a2e;
    }

    QFrame#settingsCard,
    QFrame#diagnosticCard {
        background: #152129;
        border: 1px solid #2c3a43;
        border-radius: 8px;
    }

    QFrame#settingsSection {
        background: #10181d;
        border: 1px solid #2a3942;
        border-radius: 7px;
    }
"""
