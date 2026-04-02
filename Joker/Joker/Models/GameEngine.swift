import Foundation
import Combine

// MARK: - Supporting Types

enum GameState: Equatable {
    case idle
    case dealing
    case playerTurn
    /// Waiting for the player to pick a value (and optionally a Joker action).
    case choosingWildValue(cardID: UUID, isJokerSpecial: Bool)
    case dealerTurn
    case roundOver(result: RoundResult)
}

enum RoundResult: Equatable {
    case playerWins
    case dealerWins
    case push
    case playerBust
    case dealerBust
}

enum Difficulty: String, CaseIterable {
    case easy   = "Easy"
    case normal = "Normal"
    case hard   = "Hard"

    var dealerStandThreshold: Int {
        switch self {
        case .easy:   return 14
        case .normal: return 17
        case .hard:   return 19
        }
    }
}

enum DealerEffect: Equatable {
    case skipNextDraw
    case discardCard
    case drawExtra(Int)
}

// MARK: - Game Engine

final class GameEngine: ObservableObject {

    // MARK: Published state

    @Published private(set) var playerHand: [Card] = []
    @Published private(set) var dealerHand: [Card] = []
    @Published private(set) var gameState: GameState = .idle
    @Published private(set) var pendingDealerEffects: [DealerEffect] = []
    @Published private(set) var jokerUsed: Bool = false
    @Published private(set) var wins: Int = 0
    @Published private(set) var losses: Int = 0
    @Published private(set) var pushes: Int = 0
    @Published var lastActionMessage: String = ""

    // MARK: Settings

    var difficulty: Difficulty = .normal

    // MARK: Private

    private var deck = Deck()

    // MARK: - Score helpers

    func handScore(_ hand: [Card]) -> Int {
        hand.filter(\.isFaceUp).reduce(0) { $0 + $1.pointValue }
    }

    var playerScore: Int { handScore(playerHand) }

    /// Only counts face-up dealer cards (hides hole card during player turn)
    var dealerVisibleScore: Int {
        dealerHand.filter(\.isFaceUp).reduce(0) { $0 + $1.pointValue }
    }

    var dealerScore: Int { handScore(dealerHand) }

    // MARK: - Round lifecycle

    func startNewRound() {
        playerHand             = []
        dealerHand             = []
        pendingDealerEffects   = []
        lastActionMessage      = ""

        if deck.count < 10 { deck = Deck() }

        gameState = .dealing

        // Two player cards face-up, one dealer face-up, one dealer face-down (hole)
        if let c = deck.deal()         { playerHand.append(c) }
        if let c = deck.dealFaceDown() { dealerHand.append(c) }
        if let c = deck.deal()         { playerHand.append(c) }
        if let c = deck.deal()         { dealerHand.append(c) }

        gameState = .playerTurn
        checkNaturalBlackjack()
    }

    private func checkNaturalBlackjack() {
        if playerScore == 21 {
            revealDealerCards()
            endRound()
        }
    }

    // MARK: - Player actions

    func playerHit() {
        guard gameState == .playerTurn else { return }
        guard let card = deck.deal() else { return }
        playerHand.append(card)
        if playerScore > 21 {
            gameState = .roundOver(result: .playerBust)
            updateStats(result: .playerBust)
        }
    }

    func playerStand() {
        guard gameState == .playerTurn else { return }
        revealDealerCards()
        runDealerTurn()
    }

    func playerPlayActionCard(cardID: UUID) {
        guard gameState == .playerTurn else { return }
        guard let idx = playerHand.firstIndex(where: { $0.id == cardID }) else { return }
        let card = playerHand[idx]
        guard card.isActionCard else { return }
        playerHand.remove(at: idx)
        applyActionCard(card)
    }

    // MARK: - Action card resolution

    private func applyActionCard(_ card: Card) {
        switch card.type {
        case .skip:
            pendingDealerEffects.append(.skipNextDraw)
            lastActionMessage = "Dealer skips their next draw! ⊘"

        case .reverse:
            pendingDealerEffects.append(.discardCard)
            lastActionMessage = "Dealer must discard a card! ↺"

        case .drawTwo:
            pendingDealerEffects.append(.drawExtra(2))
            lastActionMessage = "Dealer draws 2 extra cards! +2"

        case .drawFour:
            pendingDealerEffects.append(.drawExtra(4))
            lastActionMessage = "Dealer draws 4 extra cards! +4"

        case .wild:
            playerHand.append(card)
            gameState = .choosingWildValue(cardID: card.id, isJokerSpecial: false)

        case .joker:
            let isSpecial = !jokerUsed
            if isSpecial { jokerUsed = true }
            playerHand.append(card)
            gameState = .choosingWildValue(cardID: card.id, isJokerSpecial: isSpecial)
            lastActionMessage = isSpecial
                ? "🃏 Joker! Choose value AND a dealer action!"
                : "🃏 Joker used as Wild (special action already used)"

        case .number:
            break
        }
    }

    func assignWildValue(_ value: Int, cardID: UUID, jokerAction: DealerEffect? = nil) {
        guard let idx = playerHand.firstIndex(where: { $0.id == cardID }) else { return }
        playerHand[idx].assignedValue = value
        playerHand[idx].isFaceUp = true

        if let action = jokerAction {
            pendingDealerEffects.append(action)
        }

        lastActionMessage = "Wild set to \(value)!"
        gameState = .playerTurn

        if playerScore > 21 {
            gameState = .roundOver(result: .playerBust)
            updateStats(result: .playerBust)
        }
    }

    // MARK: - Dealer turn

    private func revealDealerCards() {
        for i in dealerHand.indices { dealerHand[i].isFaceUp = true }
    }

    private func runDealerTurn() {
        gameState = .dealerTurn

        var skipsRemaining = 0

        for effect in pendingDealerEffects {
            switch effect {
            case .skipNextDraw:
                skipsRemaining += 1

            case .discardCard:
                if !dealerHand.isEmpty {
                    dealerHand.removeLast()
                }

            case .drawExtra(let n):
                for _ in 0 ..< n {
                    if let card = deck.deal() { dealerHand.append(card) }
                }
            }
        }
        pendingDealerEffects = []

        // Standard draw loop, consuming skips
        while dealerScore < difficulty.dealerStandThreshold {
            if skipsRemaining > 0 {
                skipsRemaining -= 1
                continue  // skip this draw opportunity but keep checking threshold
            }
            guard let card = deck.deal() else { break }
            dealerHand.append(card)
        }

        endRound()
    }

    // MARK: - Round end

    private func endRound() {
        let ps = playerScore
        let ds = dealerScore

        let result: RoundResult
        if ps > 21 {
            result = .playerBust
        } else if ds > 21 {
            result = .dealerBust
        } else if ps > ds {
            result = .playerWins
        } else if ds > ps {
            result = .dealerWins
        } else {
            result = .push
        }

        updateStats(result: result)
        gameState = .roundOver(result: result)
    }

    private func updateStats(result: RoundResult) {
        switch result {
        case .playerWins, .dealerBust: wins   += 1
        case .dealerWins, .playerBust: losses += 1
        case .push:                    pushes += 1
        }
    }

    func resetStats() {
        wins = 0; losses = 0; pushes = 0
    }
}
