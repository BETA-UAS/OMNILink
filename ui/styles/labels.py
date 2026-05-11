LABEL_STYLES = """
    QLabel {
        background: transparent;
    }

    QLabel#appTitle {
        color: #0f1f33;
        font-size: 23px;
        font-weight: 900;
    }

    QLabel#appSubtitle,
    QLabel#mutedInfo {
        color: #627286;
        font-weight: 700;
    }

    QLabel#fieldValue {
        color: #0f1f33;
        font-size: 14px;
        font-weight: 900;
    }

    QLabel#deviceName {
        color: #1b2836;
        font-size: 12px;
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
        color: #075c39;
        background: #ddf7e8;
        border: 1px solid #78c59a;
    }

    QLabel#statusPill[state="error"] {
        color: #9a251c;
        background: #ffe5e2;
        border: 1px solid #e3a09b;
    }

    QLabel#statusDot {
        font-size: 18px;
        font-weight: 900;
    }

    QLabel#statusDot[state="ok"] {
        color: #16834f;
    }

    QLabel#statusDot[state="error"] {
        color: #c0362c;
    }
"""
