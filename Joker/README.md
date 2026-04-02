# Joker – Blackjack × Uno iOS App

A bold, cartoony iOS card game that fuses **Blackjack**'s core loop with **Uno**'s special-action mechanics.

---

## Project structure

```
Joker/
├── project.yml                          ← XcodeGen project spec
└── Joker/
    ├── JokerApp.swift                   ← App entry point (@main)
    ├── Models/
    │   ├── Card.swift                   ← Card, CardColor, CardType
    │   ├── Deck.swift                   ← Deck builder + deal helpers
    │   └── GameEngine.swift             ← Core game logic + state machine
    ├── ViewModels/
    │   └── GameViewModel.swift          ← ObservableObject bridging engine → UI
    ├── Extensions/
    │   └── Color+Theme.swift            ← Uno palette + felt colours
    └── Views/
        ├── HomeView.swift               ← Splash / main menu
        ├── GameView.swift               ← Game table (main screen)
        ├── RulesView.swift              ← Scrollable rules
        ├── SettingsView.swift           ← Difficulty, sound, haptics
        └── Components/
            ├── CardView.swift           ← Individual card rendering
            ├── HandView.swift           ← Horizontal scrollable hand
            ├── ActionButtonsView.swift  ← ActionButton + StatBadge
            ├── WildValuePickerView.swift ← Wild / Joker value + action sheet
            └── RoundResultOverlay.swift ← Win / Lose / Push modal
```

---

## How to generate the Xcode project

This project uses [XcodeGen](https://github.com/yonaskolb/XcodeGen).

```bash
# Install XcodeGen (once)
brew install xcodegen

# Generate Joker.xcodeproj
cd Joker/
xcodegen generate
open Joker.xcodeproj
```

Alternatively, create a new **iOS App** project in Xcode (SwiftUI lifecycle,
Swift 5.9, iOS 16+), delete the default `ContentView.swift`, and add all files
from `Joker/` to the target.

---

## Requirements

| Tool    | Version |
|---------|---------|
| Xcode   | 15 +    |
| iOS SDK | 16 +    |
| Swift   | 5.9 +   |

---

## Game rules (summary)

| Goal | Get closer to **21** than the dealer without busting |
|------|-------------------------------------------------------|
| Deck | Modified Uno deck — 0–9 number cards + action cards  |
| Hit  | Draw one more card                                    |
| Stand| End your turn; dealer reveals and draws              |
| Play | Activate a selected **action card** from your hand   |

### Action cards

| Card     | Effect on dealer |
|----------|-----------------|
| Skip     | Skips their next draw |
| Reverse  | Discards their last card |
| Draw +2  | Forces 2 extra draws |
| Draw +4  | Forces 4 extra draws |
| Wild     | You choose its value (1–10) |
| 🃏 Joker | Wild value **+** any action above *(once per game)* |

### Dealer stand thresholds

| Difficulty | Dealer stands at |
|------------|-----------------|
| Easy       | 14 +            |
| Normal     | 17 + *(default)*|
| Hard       | 19 +            |

---

## Design principles

- **Bold, cartoony aesthetic** — thick black outlines, saturated Uno colours
- **Clutter-free layout** — dealer at top, player at bottom, 3 action buttons
- **iOS-native feel** — SF Rounded font, spring animations, haptic feedback
- **Dark felt table** background throughout
