from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.responses import api_error, api_success
from apps.organizations.pagination import paginate_queryset
from apps.users.filters import UserFilter
from apps.users.models import User
from apps.users.serializers import UserSerializer, UserWriteSerializer


def get_user_id_param(request):
    user_id = request.query_params.get("id")
    if not user_id:
        return None, api_error(
            "id query parameter is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return user_id, None


class UserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_id = request.query_params.get("id")
        if user_id:
            user = get_object_or_404(User, pk=user_id)
            return api_success(data=UserSerializer(user).data)

        queryset = User.objects.all()
        user_filter = UserFilter(request.query_params, queryset=queryset)
        if not user_filter.is_valid():
            return api_error("Invalid filter parameters.", errors=user_filter.errors)

        response = paginate_queryset(
            request,
            user_filter.qs,
            serializer=UserSerializer,
        )
        if response is not None:
            return response

        return api_success(data=[])

    def post(self, request):
        serializer = UserWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        if User.objects.filter(email=serializer.validated_data["email"]).exists():
            return api_error("A user with this email already exists.", status_code=400)

        user = serializer.save()
        return api_success(
            data=UserSerializer(user).data,
            message="User created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def put(self, request):
        user_id, error_response = get_user_id_param(request)
        if error_response:
            return error_response

        user = get_object_or_404(User, pk=user_id)
        serializer = UserWriteSerializer(user, data=request.data)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        user = serializer.save()
        return api_success(
            data=UserSerializer(user).data,
            message="User updated successfully.",
        )

    def patch(self, request):
        user_id, error_response = get_user_id_param(request)
        if error_response:
            return error_response

        user = get_object_or_404(User, pk=user_id)
        serializer = UserWriteSerializer(user, data=request.data, partial=True)
        if not serializer.is_valid():
            return api_error("Validation error", errors=serializer.errors)

        user = serializer.save()
        return api_success(
            data=UserSerializer(user).data,
            message="User updated successfully.",
        )

    def delete(self, request):
        user_id, error_response = get_user_id_param(request)
        if error_response:
            return error_response

        user = get_object_or_404(User, pk=user_id)
        user.delete()
        return api_success(message="User deleted successfully.")
