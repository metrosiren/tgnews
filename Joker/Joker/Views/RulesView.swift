import SwiftUI

struct RulesView: View {

    var body: some View {
        ZStack {
            Color.feltDark.ignoresSafeArea()

            ScrollView {
                VStack(alignment: .leading, spacing: 20) {

                    ruleCard(
                        title: "🎯  Goal",
                        color: .unoBlue,
                        body: """
                        Get closer to 21 than the dealer without going over. \
                        Joker adds Uno-style action cards that can tip the \
                        dealer's fate in your favour.
                        """
                    )

                    ruleCard(
                        title: "🃏  The Deck",
                        color: .unoGreen,
                        body: """
                        A modified Uno deck across 4 colours (Red, Blue, Green, Yellow):
                        • One 0 and two copies of 1–9 per colour
                        • Action cards: Skip, Reverse, Draw +2 (2 per colour)
                        • 4× Wild, 4× Draw +4 (no colour)
                        • 2× Joker (no colour)
                        """
                    )

                    ruleCard(
                        title: "🔢  Card Values",
                        color: .unoYellow,
                        body: """
                        Number cards  →  face value (0 – 9)
                        Skip          →  5 pts
                        Reverse       →  5 pts
                        Draw +2       →  2 pts
                        Draw +4       →  4 pts
                        Wild          →  0 – 10  (you choose)
                        Joker         →  0 – 10  (you choose) + action
                        """
                    )

                    ruleCard(
                        title: "⚡  Action Cards",
                        color: .unoRed,
                        body: """
                        Tap a card in your hand to select it, then tap PLAY:

                        ⊘  Skip      → Dealer skips their next draw
                        ↺  Reverse   → Dealer discards one card
                        +2 Draw +2  → Dealer draws 2 extra cards
                        +4 Draw +4  → Dealer draws 4 extra cards
                        ★  Wild      → Set this card's value (1 – 10)
                        🃏 Joker     → Wild value + choose any action above
                                        (Joker special power: once per game!)
                        """
                    )

                    ruleCard(
                        title: "🎮  How to Play",
                        color: .jokerGold,
                        body: """
                        1. Cards are dealt: you receive 2 face-up cards; \
                        dealer gets 1 face-down (hole) + 1 face-up.
                        2. On your turn choose:
                           • HIT   – draw one more card
                           • STAND – end your turn and let the dealer play
                           • PLAY  – activate the selected action card
                        3. After you stand, the dealer's hole card is \
                        revealed and they draw according to their rules.
                        4. Closest to 21 wins. Going over is a bust!
                        """
                    )

                    ruleCard(
                        title: "🤖  Dealer Rules",
                        color: .unoBlue,
                        body: """
                        Easy    → Dealer stands at 14 +
                        Normal  → Dealer stands at 17 +  (default)
                        Hard    → Dealer stands at 19 +

                        All your action-card effects are applied before \
                        the dealer draws.
                        """
                    )

                    ruleCard(
                        title: "🏆  Winning & Scoring",
                        color: .unoGreen,
                        body: """
                        Player wins  → closer to 21, or dealer busts
                        Dealer wins  → closer to 21, or player busts
                        Push         → equal scores (tie)

                        Your W / L / P stats are tracked each session.
                        """
                    )
                }
                .padding(20)
                .padding(.bottom, 32)
            }
        }
        .navigationTitle("Rules")
        .navigationBarTitleDisplayMode(.large)
    }

    // MARK: - Rule card component

    private func ruleCard(title: String, color: Color, body: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title)
                .font(.system(size: 20, weight: .black, design: .rounded))
                .foregroundColor(color)

            Text(body)
                .font(.system(size: 14, weight: .regular, design: .rounded))
                .foregroundColor(.white.opacity(0.82))
                .lineSpacing(5)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(Color.white.opacity(0.06))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(color.opacity(0.3), lineWidth: 1.5)
                )
        )
    }
}
