package ru.signflow.recommendationservice.config;

import build.buf.protovalidate.ValidationResult;
import build.buf.protovalidate.Validator;
import build.buf.protovalidate.ValidatorFactory;
import build.buf.protovalidate.exceptions.ValidationException;
import com.google.protobuf.Message;
import com.google.protobuf.Timestamp;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import ru.signflow.recommendationservice.grpc.CategoryVisitStat;
import ru.signflow.recommendationservice.grpc.EventCandidate;
import ru.signflow.recommendationservice.grpc.GetRecommendationsRequest;
import ru.signflow.recommendationservice.grpc.GetRecommendationsResponse;
import ru.signflow.recommendationservice.grpc.Recommendation;

import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.params.provider.Arguments.arguments;

class ValidationConfigTest {

    private final Validator validator =
            ValidatorFactory.newBuilder().build();

    @ParameterizedTest(name = "{0}")
    @MethodSource("validationCases")
    void shouldValidateMessage(String scenario, Message message, boolean expectedValid) throws ValidationException {
        ValidationResult result = validator.validate(message);

        assertEquals(
                expectedValid,
                result.isSuccess(),
                () -> scenario + ": " + result
        );
    }

    static Stream<Arguments> validationCases() {
        return Stream.of(
                arguments("Корректная статистика", stat(7, 3), true),
                arguments("Ноль посещений допустим", stat(7, 0), true),
                arguments("Нулевой ID категории", stat(0, 3), false),
                arguments("Отрицательный ID категории", stat(-1, 3), false),
                arguments("Отрицательное число посещений", stat(7, -1), false),


                arguments("Корректный кандидат", event(1, 7, 12), true),
                arguments("Пустые категории допустимы", event(1), true),
                arguments("Повтор категории допустим", event(1, 7, 7), true),
                arguments("Нулевой ID мероприятия", event(0, 7), false),
                arguments("Отрицательный ID мероприятия", event(-1, 7), false),
                arguments("Нулевая категория кандидата", event(1, 7, 0), false),
                arguments("Отрицательная категория кандидата", event(1, -1), false),
                arguments("Отсутствует время начала",
                        event(1, 7).toBuilder().clearStartsAt().build(), false),


                arguments("Корректный запрос", request().build(), true),
                arguments("Минимальный положительный limit",
                        request().setLimit(1).build(), true),
                arguments("Нулевой limit",
                        request().setLimit(0).build(), false),
                arguments("Отрицательный limit",
                        request().setLimit(-1).build(), false),
                arguments("Пустая история",
                        request().clearCategoryStats().build(), true),
                arguments("Пустой список кандидатов",
                        request().clearCandidates().build(), true),


                arguments("Повтор ID категории в статистике",
                        request().addCategoryStats(stat(7, 9)).build(), false),
                arguments("Повтор ID мероприятия в кандидатах",
                        request().addCandidates(event(1, 12)).build(), false),

                arguments("Некорректная статистика внутри запроса",
                        request().setCategoryStats(0, stat(7, -1)).build(), false),
                arguments("Некорректный кандидат внутри запроса",
                        request().setCandidates(0, event(0, 7)).build(), false),


                arguments("Корректная рекомендация", recommendation(1, 5), true),
                arguments("Нулевой балл допустим", recommendation(1, 0), true),
                arguments("Нулевой ID рекомендации", recommendation(0, 5), false),
                arguments("Отрицательный ID рекомендации",
                        recommendation(-1, 5), false),
                arguments("Отрицательный балл", recommendation(1, -1), false),


                arguments("Пустой ответ",
                        GetRecommendationsResponse.getDefaultInstance(), true),
                arguments("Корректный ответ",
                        GetRecommendationsResponse.newBuilder()
                                .addRecommendations(recommendation(1, 5))
                                .addRecommendations(recommendation(2, 0))
                                .build(), true),
                arguments("Некорректная рекомендация внутри ответа",
                        GetRecommendationsResponse.newBuilder()
                                .addRecommendations(recommendation(1, 5))
                                .addRecommendations(recommendation(2, -1))
                                .build(), false)
        );
    }

    private static CategoryVisitStat stat(long categoryId, int count) {
        return CategoryVisitStat.newBuilder()
                .setCategoryId(categoryId)
                .setVisitCount(count)
                .build();
    }

    private static EventCandidate event(long eventId, long... categoryIds) {
        EventCandidate.Builder builder = EventCandidate.newBuilder()
                .setEventId(eventId)
                .setStartsAt(Timestamp.newBuilder().setSeconds(1).build());

        for (long categoryId : categoryIds) {
            builder.addCategoryIds(categoryId);
        }

        return builder.build();
    }

    private static GetRecommendationsRequest.Builder request() {
        return GetRecommendationsRequest.newBuilder()
                .addCategoryStats(stat(7, 3))
                .addCandidates(event(1, 7))
                .setLimit(3);
    }

    private static Recommendation recommendation(long eventId, long score) {
        return Recommendation.newBuilder()
                .setEventId(eventId)
                .setScore(score)
                .build();
    }
}