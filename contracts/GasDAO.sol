// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Address.sol";
import "@openzeppelin/contracts/utils/structs/EnumerableSet.sol";

interface IFreedomToken {
    function getVotes(address account) external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function delegate(address delegatee) external;
    function delegates(address account) external view returns (address);
}

/**
 * @title GasDAO
 * @author FreedomToken Team
 * @notice Decentralized governance DAO for protocol decisions
 * @dev Implements proposal creation, voting, timelock, and execution
 *      with quadratic voting and delegation support
 * @custom:security-contact security@freedomtoken.io
 */
contract GasDAO is AccessControl, ReentrancyGuard {
    using Address for address;
    using EnumerableSet for EnumerableSet.AddressSet;

    // ============ Roles ============
    bytes32 public constant EXECUTOR_ROLE = keccak256("EXECUTOR_ROLE");
    bytes32 public constant PROPOSER_ROLE = keccak256("PROPOSER_ROLE");
    bytes32 public constant GUARDIAN_ROLE = keccak256("GUARDIAN_ROLE");
    bytes32 public constant AI_CONTROLLER_ROLE = keccak256("AI_CONTROLLER_ROLE");

    // ============ Proposal Struct ============
    enum ProposalState {
        Pending,
        Active,
        Canceled,
        Defeated,
        Succeeded,
        Queued,
        Expired,
        Executed
    }

    enum VoteType {
        Against,
        For,
        Abstain
    }

    struct Proposal {
        uint256 id;
        address proposer;
        address[] targets;
        uint256[] values;
        bytes[] calldatas;
        string description;
        bytes32 descriptionHash;
        uint256 forVotes;
        uint256 againstVotes;
        uint256 abstainVotes;
        uint256 startBlock;
        uint256 endBlock;
        uint256 eta;
        bool canceled;
        bool executed;
        mapping(address => bool) hasVoted;
        mapping(address => uint8) support;
    }

    // ============ Governance Parameters ============
    IFreedomToken public immutable governanceToken;
    
    uint256 public constant PROPOSAL_THRESHOLD = 10000 * 10**18; // 10K tokens
    uint256 public constant QUORUM_VOTES = 100000 * 10**18; // 100K tokens (10% of initial)
    uint256 public constant PROPOSAL_MAX_OPERATIONS = 10;
    uint256 public constant VOTING_DELAY = 1; // 1 block
    uint256 public constant VOTING_PERIOD = 50400; // ~7 days (assuming 12s blocks)
    uint256 public constant TIMELOCK_DELAY = 2 days;
    uint256 public constant GRACE_PERIOD = 14 days;
    uint256 public constant PROPOSAL_THRESHOLD_PERCENT = 1; // 1% of supply

    // ============ Storage ============
    mapping(uint256 => Proposal) public proposals;
    uint256 public proposalCount;
    mapping(bytes32 => bool) public queuedTransactions;
    EnumerableSet.AddressSet private _proposers;
    
    // ============ AI Integration ============
    struct AIRecommendation {
        uint256 proposalId;
        string recommendation;
        uint8 confidence; // 0-100
        uint256 timestamp;
        bool implemented;
    }
    
    mapping(uint256 => AIRecommendation) public aiRecommendations;
    
    // ============ Events ============
    event ProposalCreated(
        uint256 indexed id,
        address indexed proposer,
        address[] targets,
        uint256[] values,
        string[] signatures,
        bytes[] calldatas,
        uint256 startBlock,
        uint256 endBlock,
        string description
    );
    event VoteCast(
        address indexed voter,
        uint256 indexed proposalId,
        uint8 support,
        uint256 votes,
        string reason
    );
    event ProposalCanceled(uint256 indexed id);
    event ProposalQueued(uint256 indexed id, uint256 eta);
    event ProposalExecuted(uint256 indexed id);
    event AIRecommendationAdded(
        uint256 indexed proposalId,
        string recommendation,
        uint8 confidence
    );
    event TimelockTransactionQueued(
        bytes32 indexed txHash,
        address indexed target,
        uint256 value,
        string signature,
        bytes data,
        uint256 eta
    );
    event TimelockTransactionExecuted(
        bytes32 indexed txHash,
        address indexed target,
        uint256 value,
        string signature,
        bytes data
    );
    event GuardianAction(string action, uint256 proposalId, string reason);

    // ============ Errors ============
    error InvalidProposalLength(uint256 targets, uint256 values, uint256 calldatas);
    error ProposalThresholdNotMet(address proposer, uint256 votes, uint256 threshold);
    error ProposalNotFound(uint256 proposalId);
    error InvalidProposalState(uint256 proposalId, ProposalState current, ProposalState required);
    error VotingNotStarted(uint256 proposalId, uint256 startBlock);
    error VotingEnded(uint256 proposalId, uint256 endBlock);
    error AlreadyVoted(uint256 proposalId, address voter);
    error InvalidVoteType(uint8 voteType);
    error QuorumNotReached(uint256 forVotes, uint256 againstVotes, uint256 quorum);
    error ProposalDefeated(uint256 forVotes, uint256 againstVotes);
    error TimelockNotExpired(uint256 proposalId, uint256 eta, uint256 currentTime);
    error TimelockExpired(uint256 proposalId, uint256 eta, uint256 gracePeriodEnd);
    error ExecutionFailed(uint256 proposalId, uint256 operationIndex);
    error ProposalTooManyActions(uint256 actions, uint256 max);
    error InvalidValueArray(uint256 length);
    error TransactionNotQueued(bytes32 txHash);
    error TransactionAlreadyQueued(bytes32 txHash);
    error TransactionStale(bytes32 txHash, uint256 eta);
    error TransactionExecutionFailed(bytes32 txHash);

    // ============ Modifiers ============
    modifier onlyProposer(uint256 proposalId) {
        require(
            proposals[proposalId].proposer == msg.sender,
            "GasDAO: only proposer can cancel"
        );
        _;
    }

    // ============ Constructor ============
    /**
     * @notice Initializes GasDAO with governance token
     * @param _governanceToken Address of FreedomToken contract
     * @param _admin Address with admin role
     * @param _guardian Emergency guardian address
     * @param _aiController AI controller address
     */
    constructor(
        address _governanceToken,
        address _admin,
        address _guardian,
        address _aiController
    ) {
        if (_governanceToken == address(0)) revert InvalidProposalLength(0, 0, 0);
        if (_admin == address(0)) revert InvalidProposalLength(0, 0, 0);
        
        governanceToken = IFreedomToken(_governanceToken);
        
        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(EXECUTOR_ROLE, _admin);
        _grantRole(PROPOSER_ROLE, _admin);
        _grantRole(GUARDIAN_ROLE, _guardian);
        _grantRole(AI_CONTROLLER_ROLE, _aiController);
    }

    // ============ Proposal Creation ============
    /**
     * @notice Creates a new governance proposal
     * @param targets Contract addresses to call
     * @param values ETH values to send
     * @param calldatas Encoded function calls
     * @param description Human-readable description
     * @return proposalId ID of created proposal
     */
    function propose(
        address[] memory targets,
        uint256[] memory values,
        bytes[] memory calldatas,
        string memory description
    ) external onlyRole(PROPOSER_ROLE) returns (uint256) {
        return _createProposal(targets, values, calldatas, description);
    }

    /**
     * @notice Internal function to create proposal
     */
    function _createProposal(
        address[] memory targets,
        uint256[] memory values,
        bytes[] memory calldatas,
        string memory description
    ) internal returns (uint256) {
        // Validate inputs
        if (
            targets.length != values.length ||
            targets.length != calldatas.length
        ) {
            revert InvalidProposalLength(targets.length, values.length, calldatas.length);
        }
        
        if (targets.length == 0) {
            revert InvalidProposalLength(0, 0, 0);
        }
        
        if (targets.length > PROPOSAL_MAX_OPERATIONS) {
            revert ProposalTooManyActions(targets.length, PROPOSAL_MAX_OPERATIONS);
        }
        
        // Check proposal threshold
        uint256 proposerVotes = governanceToken.getVotes(msg.sender);
        if (proposerVotes < PROPOSAL_THRESHOLD) {
            revert ProposalThresholdNotMet(msg.sender, proposerVotes, PROPOSAL_THRESHOLD);
        }
        
        uint256 proposalId = proposalCount++;
        Proposal storage newProposal = proposals[proposalId];
        
        newProposal.id = proposalId;
        newProposal.proposer = msg.sender;
        newProposal.targets = targets;
        newProposal.values = values;
        newProposal.calldatas = calldatas;
        newProposal.description = description;
        newProposal.descriptionHash = keccak256(bytes(description));
        newProposal.startBlock = block.number + VOTING_DELAY;
        newProposal.endBlock = block.number + VOTING_DELAY + VOTING_PERIOD;
        
        _proposers.add(msg.sender);
        
        // Extract signatures for event (optional, for logging)
        string[] memory signatures = new string[](calldatas.length);
        
        emit ProposalCreated(
            proposalId,
            msg.sender,
            targets,
            values,
            signatures,
            calldatas,
            newProposal.startBlock,
            newProposal.endBlock,
            description
        );
        
        return proposalId;
    }

    // ============ AI Proposal Integration ============
    /**
     * @notice Creates AI-assisted proposal with recommendation
     * @param targets Contract addresses
     * @param values ETH values
     * @param calldatas Encoded calls
     * @param description Human description
     * @param aiRecommendation AI analysis
     * @param confidence AI confidence score (0-100)
     * @return proposalId Created proposal ID
     */
    function proposeWithAIRecommendation(
        address[] memory targets,
        uint256[] memory values,
        bytes[] memory calldatas,
        string memory description,
        string memory aiRecommendation,
        uint8 confidence
    ) external onlyRole(AI_CONTROLLER_ROLE) returns (uint256) {
        uint256 proposalId = _createProposal(targets, values, calldatas, description);
        
        aiRecommendations[proposalId] = AIRecommendation({
            proposalId: proposalId,
            recommendation: aiRecommendation,
            confidence: confidence,
            timestamp: block.timestamp,
            implemented: false
        });
        
        emit AIRecommendationAdded(proposalId, aiRecommendation, confidence);
        return proposalId;
    }

    /**
     * @notice Get AI recommendation for proposal
     * @param proposalId Proposal to query
     */
    function getAIRecommendation(uint256 proposalId) external view returns (
        string memory recommendation,
        uint8 confidence,
        uint256 timestamp,
        bool implemented
    ) {
        AIRecommendation storage rec = aiRecommendations[proposalId];
        return (rec.recommendation, rec.confidence, rec.timestamp, rec.implemented);
    }

    // ============ Voting ============
    /**
     * @notice Cast vote on proposal
     * @param proposalId Proposal to vote on
     * @param support Vote type (0=Against, 1=For, 2=Abstain)
     */
    function castVote(uint256 proposalId, uint8 support) external {
        castVoteWithReason(proposalId, support, "");
    }

    /**
     * @notice Cast vote with reason
     * @param proposalId Proposal to vote on
     * @param support Vote type
     * @param reason Explanation for vote
     */
    function castVoteWithReason(
        uint256 proposalId,
        uint8 support,
        string memory reason
    ) public nonReentrant {
        if (support > uint8(VoteType.Abstain)) {
            revert InvalidVoteType(support);
        }
        
        Proposal storage proposal = proposals[proposalId];
        
        if (proposal.proposer == address(0)) {
            revert ProposalNotFound(proposalId);
        }
        
        if (state(proposalId) != ProposalState.Active) {
            revert InvalidProposalState(proposalId, state(proposalId), ProposalState.Active);
        }
        
        if (proposal.hasVoted[msg.sender]) {
            revert AlreadyVoted(proposalId, msg.sender);
        }
        
        uint256 votes = governanceToken.getVotes(msg.sender);
        if (votes == 0) revert ProposalThresholdNotMet(msg.sender, 0, 1);
        
        proposal.hasVoted[msg.sender] = true;
        proposal.support[msg.sender] = support;
        
        if (support == uint8(VoteType.Against)) {
            proposal.againstVotes += votes;
        } else if (support == uint8(VoteType.For)) {
            proposal.forVotes += votes;
        } else {
            proposal.abstainVotes += votes;
        }
        
        emit VoteCast(msg.sender, proposalId, support, votes, reason);
    }

    /**
     * @notice Check if address has voted on proposal
     * @param proposalId Proposal to check
     * @param account Address to check
     */
    function hasVoted(uint256 proposalId, address account) external view returns (bool) {
        return proposals[proposalId].hasVoted[account];
    }

    // ============ Proposal State ============
    /**
     * @notice Get current state of proposal
     * @param proposalId Proposal to check
     * @return Current state enum value
     */
    function state(uint256 proposalId) public view returns (ProposalState) {
        Proposal storage proposal = proposals[proposalId];
        
        if (proposal.proposer == address(0)) {
            revert ProposalNotFound(proposalId);
        }
        
        if (proposal.canceled) {
            return ProposalState.Canceled;
        }
        
        if (proposal.executed) {
            return ProposalState.Executed;
        }
        
        if (block.number <= proposal.startBlock) {
            return ProposalState.Pending;
        }
        
        if (block.number <= proposal.endBlock) {
            return ProposalState.Active;
        }
        
        if (proposal.forVotes <= proposal.againstVotes ||
            proposal.forVotes + proposal.abstainVotes < QUORUM_VOTES) {
            return ProposalState.Defeated;
        }
        
        if (proposal.eta == 0) {
            return ProposalState.Succeeded;
        }
        
        if (block.timestamp >= proposal.eta + GRACE_PERIOD) {
            return ProposalState.Expired;
        }
        
        if (proposal.executed) {
            return ProposalState.Executed;
        }
        
        return ProposalState.Queued;
    }

    // ============ Execution ============
    /**
     * @notice Queue successful proposal for execution
     * @param proposalId Proposal to queue
     */
    function queue(uint256 proposalId) external {
        if (state(proposalId) != ProposalState.Succeeded) {
            revert InvalidProposalState(proposalId, state(proposalId), ProposalState.Succeeded);
        }
        
        Proposal storage proposal = proposals[proposalId];
        uint256 eta = block.timestamp + TIMELOCK_DELAY;
        proposal.eta = eta;
        
        // Queue each transaction
        for (uint256 i = 0; i < proposal.targets.length; i++) {
            bytes32 txHash = keccak256(
                abi.encode(
                    proposal.targets[i],
                    proposal.values[i],
                    proposal.calldatas[i],
                    eta
                )
            );
            
            if (queuedTransactions[txHash]) {
                revert TransactionAlreadyQueued(txHash);
            }
            
            queuedTransactions[txHash] = true;
            
            emit TimelockTransactionQueued(
                txHash,
                proposal.targets[i],
                proposal.values[i],
                "",
                proposal.calldatas[i],
                eta
            );
        }
        
        emit ProposalQueued(proposalId, eta);
    }

    /**
     * @notice Execute queued proposal
     * @param proposalId Proposal to execute
     */
    function execute(uint256 proposalId) external payable onlyRole(EXECUTOR_ROLE) nonReentrant {
        if (state(proposalId) != ProposalState.Queued) {
            revert InvalidProposalState(proposalId, state(proposalId), ProposalState.Queued);
        }
        
        Proposal storage proposal = proposals[proposalId];
        
        if (block.timestamp < proposal.eta) {
            revert TimelockNotExpired(proposalId, proposal.eta, block.timestamp);
        }
        
        if (block.timestamp > proposal.eta + GRACE_PERIOD) {
            revert TimelockExpired(proposalId, proposal.eta, proposal.eta + GRACE_PERIOD);
        }
        
        proposal.executed = true;
        
        // Execute each transaction
        for (uint256 i = 0; i < proposal.targets.length; i++) {
            bytes32 txHash = keccak256(
                abi.encode(
                    proposal.targets[i],
                    proposal.values[i],
                    proposal.calldatas[i],
                    proposal.eta
                )
            );
            
            if (!queuedTransactions[txHash]) {
                revert TransactionNotQueued(txHash);
            }
            
            queuedTransactions[txHash] = false;
            
            (bool success, ) = proposal.targets[i].call{value: proposal.values[i]}(
                proposal.calldatas[i]
            );
            
            if (!success) {
                revert ExecutionFailed(proposalId, i);
            }
            
            emit TimelockTransactionExecuted(
                txHash,
                proposal.targets[i],
                proposal.values[i],
                "",
                proposal.calldatas[i]
            );
        }
        
        emit ProposalExecuted(proposalId);
    }

    // ============ Cancellation ============
    /**
     * @notice Cancel proposal (proposer only, before voting starts)
     * @param proposalId Proposal to cancel
     */
    function cancel(uint256 proposalId) external onlyProposer(proposalId) {
        ProposalState currentState = state(proposalId);
        
        if (currentState == ProposalState.Canceled ||
            currentState == ProposalState.Executed ||
            currentState == ProposalState.Expired) {
            revert InvalidProposalState(proposalId, currentState, ProposalState.Pending);
        }
        
        Proposal storage proposal = proposals[proposalId];
        
        // Proposer can cancel before voting starts or if they lost votes
        if (currentState == ProposalState.Active) {
            uint256 proposerVotes = governanceToken.getVotes(proposal.proposer);
            if (proposerVotes >= PROPOSAL_THRESHOLD) {
                revert InvalidProposalState(proposalId, currentState, ProposalState.Pending);
            }
        }
        
        proposal.canceled = true;
        
        // Clear queued transactions
        for (uint256 i = 0; i < proposal.targets.length; i++) {
            bytes32 txHash = keccak256(
                abi.encode(
                    proposal.targets[i],
                    proposal.values[i],
                    proposal.calldatas[i],
                    proposal.eta
                )
            );
            queuedTransactions[txHash] = false;
        }
        
        emit ProposalCanceled(proposalId);
    }

    /**
     * @notice Guardian emergency cancel
     * @param proposalId Proposal to cancel
     * @param reason Reason for cancellation
     */
    function guardianCancel(uint256 proposalId, string calldata reason) external onlyRole(GUARDIAN_ROLE) {
        Proposal storage proposal = proposals[proposalId];
        proposal.canceled = true;
        
        emit GuardianAction("cancel", proposalId, reason);
        emit ProposalCanceled(proposalId);
    }

    // ============ View Functions ============
    /**
     * @notice Get proposal details
     * @param proposalId Proposal to query
     */
    function getProposal(uint256 proposalId) external view returns (
        uint256 id,
        address proposer,
        address[] memory targets,
        uint256[] memory values,
        bytes[] memory calldatas,
        string memory description,
        uint256 forVotes,
        uint256 againstVotes,
        uint256 abstainVotes,
        uint256 startBlock,
        uint256 endBlock,
        uint256 eta,
        bool canceled,
        bool executed
    ) {
        Proposal storage p = proposals[proposalId];
        return (
            p.id,
            p.proposer,
            p.targets,
            p.values,
            p.calldatas,
            p.description,
            p.forVotes,
            p.againstVotes,
            p.abstainVotes,
            p.startBlock,
            p.endBlock,
            p.eta,
            p.canceled,
            p.executed
        );
    }

    /**
     * @notice Get proposal actions count
     * @param proposalId Proposal to check
     */
    function getProposalActionsCount(uint256 proposalId) external view returns (uint256) {
        return proposals[proposalId].targets.length;
    }

    /**
     * @notice Check quorum for proposal
     * @param proposalId Proposal to check
     */
    function quorumReached(uint256 proposalId) external view returns (bool) {
        Proposal storage p = proposals[proposalId];
        return p.forVotes + p.abstainVotes >= QUORUM_VOTES;
    }

    /**
     * @notice Get all proposers
     */
    function getProposers() external view returns (address[] memory) {
        return _proposers.values();
    }

    // ============ Governance Parameters ============
    /**
     * @notice Update proposal threshold (requires governance vote)
     * @param newThreshold New threshold amount
     */
    function setProposalThreshold(uint256 newThreshold) external onlyRole(DEFAULT_ADMIN_ROLE) {
        // Implementation would update storage variable
        // For simplicity, using constant in this version
        revert("GasDAO: parameter changes require contract upgrade");
    }

    // ============ Receive ============
    receive() external payable {}
}