import SwiftUI
import UIKit
import Combine

@MainActor
final class GameViewModel: ObservableObject {

    // MARK: - Engine

    let engine = GameEngine()

    // MARK: - UI state

    @Published var selectedCardID: UUID? = nil
    @Published var showWildPicker: Bool  = false
    @Published var wildCardID: UUID?     = nil
    @Published var isJokerWild: Bool     = false
    @Published var showActionMessage: Bool = false

    // MARK: - Settings pass-through

    @AppStorage("difficulty") private var difficultyRaw: String = Difficulty.normal.rawValue

    private var cancellables = Set<AnyCancellable>()

    // MARK: - Init

    init() {
        engine.$gameState
            .receive(on: RunLoop.main)
            .sink { [weak self] state in self?.handleStateChange(state) }
            .store(in: &cancellables)

        engine.$lastActionMessage
            .receive(on: RunLoop.main)
            .filter { !$0.isEmpty }
            .sink { [weak self] _ in
                self?.showActionMessage = true
                DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                    self?.showActionMessage = false
                }
            }
            .store(in: &cancellables)

        // Sync difficulty from settings
        engine.difficulty = Difficulty(rawValue: difficultyRaw) ?? .normal
    }

    // MARK: - State handling

    private func handleStateChange(_ state: GameState) {
        switch state {
        case .choosingWildValue(let id, let isJokerSpecial):
            wildCardID   = id
            isJokerWild  = isJokerSpecial
            showWildPicker = true
        default:
            if showWildPicker { showWildPicker = false }
        }
    }

    // MARK: - Computed helpers

    var playerScore: Int      { engine.playerScore }
    var dealerVisibleScore: Int { engine.dealerVisibleScore }
    var gameState: GameState  { engine.gameState }
    var playerHand: [Card]    { engine.playerHand }
    var dealerHand: [Card]    { engine.dealerHand }
    var jokerUsed: Bool       { engine.jokerUsed }

    var isPlayerTurn: Bool {
        if case .playerTurn = engine.gameState { return true }
        return false
    }

    var selectedCard: Card? {
        guard let id = selectedCardID else { return nil }
        return engine.playerHand.first(where: { $0.id == id })
    }

    var selectedCardIsActionCard: Bool {
        selectedCard?.isActionCard ?? false
    }

    // MARK: - Actions

    func startRound() {
        selectedCardID = nil
        engine.difficulty = Difficulty(rawValue: difficultyRaw) ?? .normal
        engine.startNewRound()
    }

    func hit() {
        selectedCardID = nil
        engine.playerHit()
        haptic(.light)
    }

    func stand() {
        selectedCardID = nil
        engine.playerStand()
        haptic(.medium)
    }

    func toggleSelection(_ id: UUID) {
        withAnimation(.spring(response: 0.25)) {
            selectedCardID = (selectedCardID == id) ? nil : id
        }
        haptic(.light)
    }

    func playSelectedActionCard() {
        guard let id = selectedCardID else { return }
        selectedCardID = nil
        engine.playerPlayActionCard(cardID: id)
        haptic(.medium)
    }

    func confirmWildValue(_ value: Int, jokerAction: DealerEffect? = nil) {
        guard let id = wildCardID else { return }
        engine.assignWildValue(value, cardID: id, jokerAction: jokerAction)
        showWildPicker = false
        wildCardID     = nil
        haptic(.success)
    }

    // MARK: - Haptics

    private func haptic(_ style: HapticStyle) {
        switch style {
        case .light:
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
        case .medium:
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        case .success:
            UINotificationFeedbackGenerator().notificationOccurred(.success)
        }
    }

    private enum HapticStyle { case light, medium, success }
}
