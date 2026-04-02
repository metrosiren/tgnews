import SwiftUI

struct GameView: View {

    @StateObject private var vm = GameViewModel()
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            // Felt background
            Color.feltDark.ignoresSafeArea()
            RadialGradient(
                colors: [Color.feltGreen, Color.feltDark],
                center: .center,
                startRadius: 0,
                endRadius: 420
            )
            .ignoresSafeArea()

            // Main layout
            VStack(spacing: 0) {
                topBar
                dealerSection
                tableDivider
                playerSection
                bottomButtons
                    .padding(.bottom, 24)
            }

            // Floating action message
            if vm.showActionMessage {
                actionToast
            }

            // Wild / Joker value picker
            if vm.showWildPicker {
                WildValuePickerView(isJokerSpecial: vm.isJokerWild) { value, jokerAction in
                    vm.confirmWildValue(value, jokerAction: jokerAction)
                }
                .transition(.opacity.combined(with: .scale(scale: 0.95)))
                .animation(.spring(response: 0.3), value: vm.showWildPicker)
                .zIndex(10)
            }

            // Round result overlay
            if case .roundOver(let result) = vm.gameState {
                RoundResultOverlay(result: result) {
                    withAnimation { vm.startRound() }
                }
                .transition(.opacity)
                .animation(.easeIn(duration: 0.25), value: vm.gameState == .playerTurn)
                .zIndex(20)
            }
        }
        .navigationBarBackButtonHidden()
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                Button { dismiss() } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.title2)
                        .foregroundColor(.white.opacity(0.65))
                }
            }
        }
        .onAppear { vm.startRound() }
    }

    // MARK: - Top bar

    private var topBar: some View {
        HStack(alignment: .center) {
            // Dealer score
            VStack(alignment: .leading, spacing: 2) {
                Text("DEALER")
                    .font(.system(size: 10, weight: .bold, design: .rounded))
                    .foregroundColor(.white.opacity(0.5))
                    .tracking(1.5)
                Text(dealerScoreText)
                    .font(.system(size: 24, weight: .black, design: .rounded))
                    .foregroundColor(.white)
                    .contentTransition(.numericText())
                    .animation(.easeInOut(duration: 0.2), value: vm.dealerVisibleScore)
            }

            Spacer()

            // W / L / P stats
            HStack(spacing: 18) {
                StatBadge(label: "W", value: vm.engine.wins,   color: .unoGreen)
                StatBadge(label: "L", value: vm.engine.losses, color: .unoRed)
                StatBadge(label: "P", value: vm.engine.pushes, color: .unoYellow)
            }

            Spacer()

            // Player score
            VStack(alignment: .trailing, spacing: 2) {
                Text("YOU")
                    .font(.system(size: 10, weight: .bold, design: .rounded))
                    .foregroundColor(.white.opacity(0.5))
                    .tracking(1.5)
                Text("\(vm.playerScore)")
                    .font(.system(size: 24, weight: .black, design: .rounded))
                    .foregroundColor(vm.playerScore > 21 ? .unoRed : .white)
                    .contentTransition(.numericText())
                    .animation(.easeInOut(duration: 0.2), value: vm.playerScore)
            }
        }
        .padding(.horizontal, 20)
        .padding(.top, 8)
        .padding(.bottom, 12)
    }

    private var dealerScoreText: String {
        let visible = vm.dealerVisibleScore
        // Show "?" when hole card is still face-down during player turn
        let hasHoleCard = vm.dealerHand.contains(where: { !$0.isFaceUp })
        if hasHoleCard {
            return visible > 0 ? "\(visible) + ?" : "?"
        }
        return "\(visible)"
    }

    // MARK: - Dealer area

    private var dealerSection: some View {
        VStack(spacing: 6) {
            Text("DEALER'S HAND")
                .font(.system(size: 10, weight: .bold, design: .rounded))
                .foregroundColor(.white.opacity(0.35))
                .tracking(2)

            HandView(
                cards: vm.dealerHand,
                selectedID: .constant(nil),
                isInteractive: false
            )
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
    }

    private var tableDivider: some View {
        Rectangle()
            .fill(Color.white.opacity(0.12))
            .frame(height: 1)
            .padding(.horizontal, 20)
    }

    // MARK: - Player area

    private var playerSection: some View {
        VStack(spacing: 6) {
            Text("YOUR HAND")
                .font(.system(size: 10, weight: .bold, design: .rounded))
                .foregroundColor(.white.opacity(0.35))
                .tracking(2)

            HandView(
                cards: vm.playerHand,
                selectedID: Binding(
                    get: { vm.selectedCardID },
                    set: { id in
                        guard let id else { return }
                        vm.toggleSelection(id)
                    }
                ),
                isInteractive: vm.isPlayerTurn
            )

            // Action card hint
            if let card = vm.selectedCard, card.isActionCard {
                actionCardHint(for: card)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                    .animation(.spring(response: 0.25), value: vm.selectedCardID)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
    }

    private func actionCardHint(for card: Card) -> some View {
        HStack(spacing: 8) {
            Image(systemName: "bolt.fill")
                .font(.caption)
                .foregroundColor(.jokerGold)
            Text(card.type.abilityDescription)
                .font(.system(size: 12, weight: .semibold, design: .rounded))
                .foregroundColor(.white)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(
            Capsule()
                .fill(Color.black.opacity(0.55))
                .overlay(Capsule().stroke(Color.jokerGold.opacity(0.5), lineWidth: 1.5))
        )
    }

    // MARK: - Bottom action buttons

    private var bottomButtons: some View {
        HStack(spacing: 10) {
            ActionButton(
                title: "HIT",
                color: .unoBlue,
                icon: "plus.circle.fill",
                isEnabled: vm.isPlayerTurn
            ) { vm.hit() }

            ActionButton(
                title: "STAND",
                color: .unoRed,
                icon: "hand.raised.fill",
                isEnabled: vm.isPlayerTurn
            ) { vm.stand() }

            ActionButton(
                title: "PLAY",
                color: vm.selectedCardIsActionCard ? .unoYellow : Color.gray.opacity(0.5),
                icon: "bolt.fill",
                isEnabled: vm.isPlayerTurn && vm.selectedCardIsActionCard
            ) { vm.playSelectedActionCard() }
        }
        .padding(.horizontal, 20)
        .padding(.top, 12)
    }

    // MARK: - Action toast

    private var actionToast: some View {
        VStack {
            Text(vm.engine.lastActionMessage)
                .font(.system(size: 15, weight: .black, design: .rounded))
                .foregroundColor(.white)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 22)
                .padding(.vertical, 12)
                .background(
                    Capsule()
                        .fill(Color.black.opacity(0.82))
                        .overlay(Capsule().stroke(Color.jokerGold, lineWidth: 2))
                )
                .shadow(radius: 8)
                .transition(.move(edge: .top).combined(with: .opacity))
                .animation(.spring(), value: vm.showActionMessage)
            Spacer()
        }
        .padding(.top, 80)
        .frame(maxWidth: .infinity)
    }
}
