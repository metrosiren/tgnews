import SwiftUI

/// Displays a horizontal scrollable row of cards.
struct HandView: View {
    let cards: [Card]
    @Binding var selectedID: UUID?
    let isInteractive: Bool

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: -18) {
                ForEach(Array(cards.enumerated()), id: \.element.id) { index, card in
                    CardView(
                        card: card,
                        isSelected: selectedID == card.id,
                        faceDown: !card.isFaceUp
                    )
                    .offset(y: selectedID == card.id ? -14 : 0)
                    .zIndex(selectedID == card.id ? 100 : Double(index))
                    .onTapGesture {
                        guard isInteractive else { return }
                        withAnimation(.spring(response: 0.25)) {
                            selectedID = (selectedID == card.id) ? nil : card.id
                        }
                    }
                    .transition(
                        .asymmetric(
                            insertion: .move(edge: .bottom).combined(with: .opacity),
                            removal:   .scale(scale: 0.6).combined(with: .opacity)
                        )
                    )
                }
            }
            .padding(.horizontal, 28)
            .padding(.vertical, 18)
            .animation(.spring(response: 0.35, dampingFraction: 0.8), value: cards.count)
        }
    }
}
