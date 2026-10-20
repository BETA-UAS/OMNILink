LABEL_STYLES = """
    QLabel {
        background: transparent;
    }

    QLabel#appTitle {
        color: #ffffff;
        font-size: 38px;
        font-weight: 900;
    }

    QLabel#appLogo {
        background: transparent;
    }

    QLabel#appSubtitle {
        color: #9ca3a3;
        font-size: 13px;
        font-weight: 900;
    }

    QLabel#headerInterface {
        color: #dbe5e4;
        font-size: 15px;
        font-weight: 800;
    }

    QLabel#mutedInfo {
        color: #9ca3a3;
        font-size: 14px;
        font-weight: 700;
    }

    QLabel#fieldValue {
        color: #ffffff;
        font-size: 16px;
        font-weight: 900;
    }

    QLabel#deviceName {
        color: #f2f2ef;
        font-size: 19px;
        font-weight: 900;
    }

    QLabel#sectionKicker {
        color: #858d8d;
        font-size: 13px;
        font-weight: 900;
    }

    QLabel#sourceName {
        color: #ffffff;
        font-size: 24px;
        font-weight: 900;
    }

    QLabel#sourcePath {
        color: #070909;
        background: #f2f2ef;
        border: 1px solid #f2f2ef;
        border-radius: 4px;
        padding: 3px 8px;
        font-size: 13px;
        font-weight: 900;
    }

    QLabel#sourceAddress {
        color: #9ca3a3;
        font-size: 18px;
        font-weight: 700;
    }

    QLabel#targetAddress {
        color: #a9bbc4;
        font-size: 17px;
        font-weight: 700;
    }

    QLabel#deviceAddress {
        color: #a9bbc4;
        font-size: 16px;
        font-weight: 700;
    }

    QLabel#panelStatus {
        color: #a7b2b6;
        font-size: 16px;
        font-weight: 800;
    }
    QLabel#panelStatus[serviceState="running"] { color: #62d6a6; }
    QLabel#panelStatus[serviceState="starting"],
    QLabel#panelStatus[serviceState="stopping"] { color: #e4ae53; }
    QLabel#panelStatus[serviceState="failed"] { color: #ef7770; }

    QLabel#footerInterface {
        color: #bdd0d7;
        font-size: 14px;
        font-weight: 700;
        padding-right: 8px;
    }

    QLabel#panelTitle {
        color: #ffffff;
        font-size: 30px;
        font-weight: 900;
    }

    QLabel#networkTitle {
        color: #ffffff;
        font-size: 22px;
        font-weight: 900;
    }

    QLabel#pageTitle,
    QLabel#settingsTitle {
        color: #ffffff;
        font-size: 26px;
        font-weight: 900;
    }

    QLabel#sectionTitle {
        color: #eef5f6;
        font-size: 17px;
        font-weight: 900;
    }

    QLabel#statusPill {
        border-radius: 11px;
        padding: 3px 10px;
        font-size: 12px;
        font-weight: 900;
        letter-spacing: 0px;
    }

    QLabel#statusPill[state="ok"] {
        color: #baf7d7;
        background: #112019;
        border: 1px solid #2e7d66;
        border-radius: 9px;
    }

    QLabel#statusPill[state="error"] {
        color: #ffd0cb;
        background: #241311;
        border: 1px solid #7e3b35;
        border-radius: 9px;
    }

    QLabel#statusDot {
        font-size: 18px;
        font-weight: 900;
    }

    QLabel#statusDot[state="ok"] {
        color: #48d79a;
    }

    QLabel#statusDot[state="error"] {
        color: #e5483f;
    }

    QLabel#statusDot[state="unchecked"] { color: #69757a; }

    QLabel#networkState { font-size: 16px; font-weight: 900; }
    QLabel#networkState[state="ok"] { color: #52c996; }
    QLabel#networkState[state="error"] { color: #df6962; }
    QLabel#networkState[state="unchecked"] { color: #899398; }

    QLabel#summaryStatus {
        color: #d9e2e2;
        font-size: 17px;
        font-weight: 900;
    }
    QLabel#summaryStatus[state="running"] { color: #62d6a6; }
    QLabel#summaryStatus[state="waiting"],
    QLabel#summaryStatus[state="starting"],
    QLabel#summaryStatus[state="stopping"] { color: #e4ae53; }
    QLabel#summaryStatus[state="failed"] { color: #ef7770; }
    QLabel#summaryStatus[state="stopped"],
    QLabel#summaryStatus[state="unchecked"] { color: #a1abad; }

    QLabel#summaryIcon {
        color: #d8e4e4;
        background: #222b2f;
        border: 1px solid #39474e;
        border-radius: 7px;
        font-size: 22px;
        font-weight: 900;
    }
"""
